# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import re
import typing

from archytas.tool_utils import AgentRef, LoopControllerRef, tool
from beaker_kernel.lib.agent import BaseAgent

from beaker_bunsen.corpus.types import QueryResult

if typing.TYPE_CHECKING:
    from beaker_kernel.lib.context import BaseContext
    from .bunsen_context import BunsenContext


logger = logging.getLogger(__name__)


class BunsenAgent(BaseAgent):

    EXAMPLE_INTRO = """
Below are some similar examples of code that may be similar or related to the current request.
If the request from the user is similar enough to one of these examples, use it to help write code to answer the user's request.
""".strip()
    EXAMPLE_OUTRO = """
""".strip()

    CODE_PROMPT_INTRO = """
Please generate {self.context.subkernel.DISPLAY_NAME} code intended to run in Jupyter kernel "{self.context.subkernel.KERNEL_NAME}".
to satisfy the user's request below.
Note that this tool should generate the code directly from the LLM and not pick a tool to generate the code. This is the
code generation tool.
""".strip()
    CODE_PROMPT_OUTRO = """
Please generate the code as if you were programming inside a Jupyter Notebook and the code is to be executed inside a cell.
You MUST wrap the code with a line containing three backticks (```) before and after the generated code.
No addtional text is needed in the response, just the code block.
""".strip()


    context: "BunsenContext"

    def __init__(
        self,
        context: "BaseContext" = None,
        tools: list = None,
        **kwargs,
    ):
        self.context = context

        super().__init__(
            context=context,
            tools=tools,
            **kwargs
        )

    async def format_examples(self, examples: list[QueryResult]) -> str:
        code_example_str = "\n\n".join(
            """
======== example {num}: {example_id} start ========
{example}
======== example {num}: {example_id} end   ========
            """.strip().format(example_id=example["record"].id, example=example["record"].content, num=num)
            for num, example in enumerate(examples, start=1)
        )
        return "\n".join([
            self.EXAMPLE_INTRO,
            code_example_str,
            self.EXAMPLE_OUTRO,
        ])


    @tool()
    async def generate_code(self, code_request: str, agent: AgentRef, loop: LoopControllerRef):
        """
        Generated code to be run in an interactive Jupyter notebook.

        Input is a full grammatically correct question about or request for an action to be performed in the current environment.
        If you need more information on how to accomplish the request, you should use the other tools prior to using this one.

        Args:
            code_request (str): A fully grammatically correct set of instructions on the code that needs to be generated.
        """

        try:
            example_future = self.context.get_examples(
                query=code_request
            )
            state_future = self.context.get_subkerkel_state_description()

            examples, state_desc = await asyncio.gather(
                example_future,
                state_future
            )

            request_prompt = f"""
User's Request:
```
{code_request}
```
""".strip()

            prompt = [
                self.CODE_PROMPT_INTRO.format(self=self),
                request_prompt,
                self.context.library_description,
            ]
            if examples:
                prompt.append(await self.format_examples(examples))
            if state_desc:
                prompt.append(state_desc)
            prompt.append(self.CODE_PROMPT_OUTRO.format(self=self))

            code_generation_prompt = "\n\n".join(prompt)
            self.context.beaker_kernel.log("bunsen_prompt_code_gen", code_generation_prompt)
            response = await agent.inspect(code_generation_prompt)
            preamble, code, coda = re.split("```\w*", response)
            loop.set_state(loop.STOP_SUCCESS)

            result = {
                "action": "code_cell",
                "language": self.context.subkernel.SLUG,
                "content": code.strip(),
            }

            return json.dumps(result)
        except Exception as err:
            logger.error(err.args, exc_info=err)

    @tool()
    async def get_source_code(self, asset_type: str, asset_name: str, agent: AgentRef, loop: LoopControllerRef) -> list[str]:
        """
        Retrieves source code for a module, class, or function code asset.

        Input is a distinct identifier that uniquely distinguishes which asset you are wanting the source code of.
        Note that as this searches over the vectorized embeddings of the code using a nearest-neighbor search it is possible
        that you will receive irrelevent results if there is not a good match found.

        Args:
            asset_type (str): The type of asset you are looking up. Should be: "module", "class", or "function".
            asset_name (str): A distinct identifier that uniquely distinguishes which asset you are wanting the source code of.

        Returns:
            list: A list of chunks (strings) of source code that should correspond with the indicated asset. Order by cosine distance.
        """

        query = f"Definition of {asset_type} {asset_name}"
        matches = agent.context.get_source_code(
            query
        )
        return matches
