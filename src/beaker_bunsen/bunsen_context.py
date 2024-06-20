import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List
from dataclasses import dataclass

from beaker_kernel.lib.autodiscovery import LIB_LOCATIONS
from beaker_kernel.lib.context import BaseContext
from beaker_kernel.lib.subkernels.base import BaseSubkernel
from beaker_kernel.lib.subkernels import autodiscover_subkernels

from .bunsen_agent import BunsenAgent
from .corpus.corpus import Corpus
from .corpus.types import QueryResult, QueryResponse

if TYPE_CHECKING:
    from beaker_kernel.kernel import LLMKernel


logger = logging.getLogger(__name__)


class EnvironmentSerializer:
    pass


@dataclass
class BunsenLibrary:
    name: str
    description: str


@dataclass
class BunsenLanguageLibraries:
    libraries: dict[str, BunsenLibrary]
    subkernel_cls: type[BaseSubkernel] | None


class BunsenContext(BaseContext):
    agent_cls: BunsenAgent
    corpus: Corpus

    enabled_subkernels: list[str]
    bunsen_config: dict[str, Any] | None
    environment_serializer: EnvironmentSerializer
    _subkernel_state: dict[str, Any] | None

    enabled_subkernels = ["python3"]

    PROMPT_INTRO: str = """
You are a diligent and thorough coding assistant that consistently delivers accurate and reliable responses to user
instructions.
""".strip()
    PROMPT_OUTRO: str = """
Please answer any user queries or perform user instructions to the best of your ability.
You should look up any information you need using the tools provided. If there is a chance that a tool has more
up-to-date knowledge then what you have been trained on, you should always use the tool to ensure you have as much
information as possible. This applies if you are are answering a question, writing code, or retrieving data to pass to a
tool.
Do not guess if you are not sure of an answer. If you are unsure of an answer, always be clear of which information you
unsure of. The user is trusting you to give factual answers and to not just guess.
""".strip()

    @classmethod
    def default_payload(cls) -> str:
        return "{}"

    def __init__(
        self,
        beaker_kernel: "LLMKernel",
        config: Dict[str, Any],
    ) -> None:
        self._subkernel_state = None
        super().__init__(beaker_kernel, self.agent_cls, config)
        corpus_dir = self.corpus_location()
        self.corpus = Corpus.from_dir(corpus_dir)
        self.bunsen_config = self._load_bunsen_config()

    def _load_bunsen_config(self) -> dict[str, Any]:
        for location in LIB_LOCATIONS:
            target = os.path.join(location, "bunsen", f"{self.slug}.json")
            if os.path.exists(target):
                with open(target) as bunsen_config_file:
                    bunsen_config = json.load(bunsen_config_file)
                return bunsen_config
        return {}

    async def setup(self, context_info=None, parent_header=None):
        return await super().setup(context_info, parent_header)

    async def post_execute(self, message):
        try:
            self._subkernel_state = await self.get_subkernel_state()
        except Exception as err:
            logger.error(msg=str(err), exc_info=err)

    def corpus_location(self) -> str | None:
        for location in LIB_LOCATIONS:
            corpus_path = os.path.join(location, "corpuses", self.slug)
            if os.path.isdir(corpus_path):
                return corpus_path
        return None


    @classmethod
    def available_subkernels(cls) -> List[BaseSubkernel]:
        if cls.enabled_subkernels:
            return cls.enabled_subkernels
        else:
            return super().available_subkernels()

    async def subkernel_state(self) -> dict[str, Any]:
        if self._subkernel_state:
            return self._subkernel_state
        else:
            result = await self.get_subkernel_state()
            return result

    @property
    def libraries(self) -> dict[str, BunsenLanguageLibraries]:
        """
        Enrich the libraries with information about the subkernel, if available.
        """
        libraries: dict[str, dict[str, str]] = self.bunsen_config.get("libraries", {})
        installed_subkernels = autodiscover_subkernels()
        output = {}
        for lang, libs in libraries.items():
            lib = BunsenLanguageLibraries(
                libraries={name: BunsenLibrary(name, description) for name, description in libs.items()},
                subkernel_cls=installed_subkernels.get(lang, None),
            )
            output[lang] = lib
        return output

    @property
    def library_description(self) -> str:
        """
        """
        if not self.libraries:
            return ""

        output = [
            "Consider the following installed libraries as your primary toolset for accomplishing tasks.",
            "You should always default to using these libraries if you can, but may use tools from other libraries if needed.",
            "",
        ]
        for lang in self.libraries.values():
            # Only include libraries that match the current subkernel
            if lang.subkernel_cls and isinstance(self.subkernel, lang.subkernel_cls):
                output.append(f'''{lang.subkernel_cls.DISPLAY_NAME} (Jupyter kernel "{lang.subkernel_cls.KERNEL_NAME}") libraries:''')
                for lib in lang.libraries.values():
                    output.append( f'''  {lib.name}:''')
                    output.extend([f'''    {line.strip()}''' for line in lib.description.splitlines() if line.strip()])
                    output.append('')  # Newline between libraries
                output.append('')  # Newline between subkernels

        return "\n".join(output)

    async def get_context_prompt(self):
        """
        Class that can be overridden by subclassing to provide context specific prompt information in to the autoprompt
        """
        return None

    async def get_subkerkel_state_description(self) -> str:
        state = await self.subkernel_state()
        output = []
        if state["variables"]:
            output.append("The coding environment's state currently has the following local variables:")
            output.extend(
                f"    `{var_name}`: `{var_value}`" for var_name, var_value in state["variables"].items()
            )
        if state["functions"]:
            output.append("The coding environment's state currently has the following local functions defined:")
            output.extend(
                f"    `{func_name}`: `{func_value}`" for func_name, func_value in state["functions"].items()
            )
        if state["modules"]:
            output.append("The coding environment's state currently has the following modules imported:")
            output.extend(
                f"    `{mod_name}`: `{mod_value}`" for mod_name, mod_value in state["modules"].items()
            )
        return "\n".join(output)

    async def get_documentation_string(self) -> str:
        docs = await self.get_documentation(query=self.current_llm_query)
        if docs:
            document_str = "\n\n".join(
                """
======== documentation excerpt {num}: {document_id} start ========
{document}
======== documentation excerpt {num}: {document_id} end   ========
                """.strip().format(document_id=document["record"].id, document=document["record"].content, num=num)
                for num, document in enumerate(docs, start=1)
            )
            return "\n".join([
                """Below are some excerpts from the documentation that help you. Please use them if they are relevent.""",
                document_str,
            ])
        else:
            return None


    async def get_examples(
        self,
        query=None,
        count=5,
    ) -> list[QueryResult]:
        if query is None:
            query = self.current_llm_query
        if query:
            examples = await self.query_corpus(
                query_str=query,
                partition="code",
                limit=count,
            )
            return examples["matches"]
        return None

    async def get_documentation(
        self,
        query=None,
        count=3,
    ) -> list[QueryResult] | None:
        if query is None:
            query = self.current_llm_query

        if query:
            docs = await self.query_corpus(
                query_str=query,
                partition="documentation",
                limit=count,
            )
            return docs["matches"]
        return None

    async def get_source_code(
        self,
        query=None,
        count=3,
    ):
        matches = self.corpus.store.query(
            query_string=query,
            partition="code",
            limit=count,
        )["matches"]
        return matches

    async def build_prompt(
            self,
        ) -> str:

        state_description_future = self.get_subkerkel_state_description()
        context_prompt_future = self.get_context_prompt()
        docs_future = self.get_documentation_string()

        state_description, context_prompt, docs_result = await asyncio.gather(
            state_description_future,
            context_prompt_future,
            docs_future
        )

        prompt = [
            self.PROMPT_INTRO,
            self.library_description,
            state_description,
            docs_result,
            context_prompt,
            self.PROMPT_OUTRO,
        ]

        result = "\n".join(part for part in prompt if part)
        return result


    async def auto_context(self):
        prompt = await self.build_prompt()
        self.beaker_kernel.log("auto_context", prompt)
        return prompt


    async def query_corpus(
        self,
        query_str: str,
        partition: str = "default",
        limit: int = 5,
    ) -> QueryResponse:
        results = self.corpus.store.query(
            query_string=query_str,
            partition=partition,
            limit=limit,
        )
        return results
