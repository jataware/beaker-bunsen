# -*- coding: utf-8 -*-
import json
import logging
import re
import typing

from archytas.react import ReActAgent, Undefined
from archytas.tool_utils import AgentRef, LoopControllerRef, tool
from archytas.tool_utils import AgentRef, LoopControllerRef, ReactContextRef, tool
from beaker_kernel.lib.utils import togglable_tool

if typing.TYPE_CHECKING:
    from .bunsen_context import BunsenContext

logger = logging.getLogger(__name__)


class BunsenAgent(ReActAgent):

    context: "BunsenContext"

    def __init__(
        self,
        context: "BaseContext" = None,
        tools: list = None,
        **kwargs,
    ):
        self.context = context

        self.context.beaker_kernel.debug(
            "init-agent",
            {
                "debug": self.context.beaker_kernel.debug_enabled,
                "verbose": self.context.beaker_kernel.verbose,
            },
        )
        super().__init__(
            tools=tools,
            verbose=self.context.beaker_kernel.verbose,
            max_errors=5,
            spinner=None,
            rich_print=False,
            allow_ask_user=False,
            thought_handler=context.beaker_kernel.handle_thoughts,
            **kwargs,
        )

    def get_info(self):
        """ """
        info = {
            "name": self.__class__.__name__,
            "tools": {tool_name: tool_func.__doc__.strip() for tool_name, tool_func in self.tools.items()},
            "agent_prompt": self.__class__.__doc__.strip(),
        }
        return info

    def debug(self, event_type: str, content: typing.Any = None) -> None:
        self.context.beaker_kernel.debug(event_type=f"agent_{event_type}", content=content)
        logger.error(f"Archytas debug: {event_type} -- {content}")
        return super().debug(event_type=event_type, content=content)

    def display_observation(self, observation):
        content = {"observation": observation}
        parent_header = {}
        self.context.send_response(
            stream="iopub",
            msg_or_type="llm_observation",
            content=content,
            parent_header=parent_header,
        )
        return super().display_observation(observation)

    @togglable_tool("ENABLE_USER_PROMPT")
    async def ask_user(
        self,
        query: str,
        agent: AgentRef,
        loop: LoopControllerRef,
        react_context: ReactContextRef,
    ) -> str:
        """
        Sends a query to the user and returns their response

        Args:
            query (str): A fully grammatically correct question for the user.

        Returns:
            str: The user's response to the query.
        """
        return await self.context.beaker_kernel.prompt_user(query, parent_message=react_context.get("message", None))


# ========================


import contextlib
import importlib
import inspect
import io
import json
import logging
import re

from archytas.tool_utils import AgentRef, LoopControllerRef, tool, toolset
from askem_beaker.contexts.mira.new_base_agent import NewBaseAgent

from beaker_kernel.lib.agent import BaseAgent
from beaker_kernel.lib.context import BaseContext

logger = logging.getLogger(__name__)

CONTEXT_JSON = """
{
    "slug": "beaker_mira",
    "package": "beaker_mira_context.context",
    "class_name": "Context",
    "library_names": [
        "mira"
    ],
    "library_descriptions": [
        "mira is a framework for representing systems using ontology-grounded meta-model templates, and generating various model implementations and exchange formats from these templates. It also implements algorithms for assembling and querying domain knowledge graphs in support of modeling."
    ],
    "library_submodule_descriptions": [
        "mira.dkg - This module contains code for the construction of domain knowledge graphs.",
        "mira.modeling - This module contains code for modeling. The top level contains the Model class, together with the Variable, Transition, and ModelParameter classes, used to represent a Model.",
        "mira.metamodel - This module contains information on code related to meta models.",
        "mira.sources - This module contains code to access models from different sources like json, url, etc..",
        "mira.terarium_client - This module contains code which allows access to the terarium client. A web application for modeling. This module is not to be used.",
        "mira.examples - This module contains examples of how to assemble and modify models in mira."
    ],
    "class_examples": [
        "mira.modeling.triples.Triple"
    ],
    "function_examples": [
        "mira.metamodel.io.model_from_json_file"
    ],
    "class_method_example": [
        "mira.metamodel.template_model.TemplateModel.get_parameters_from_rate_law"
    ],
    "submodule_examples": [
        "mira.modeling"
    ],
    "documentation_query_examples": [
        "'ode model', 'sir model', 'using dkg package'"
    ],
    "task_description": "Modeling and Visualization"
}
"""


@toolset()
class Toolset:
    """Toolset for our context"""

    @tool(autosummarize=True)
    async def compare_models(self, model_vars: list, agent: AgentRef, loop: LoopControllerRef) -> str:
        """
        Use this tool to compare models and visualize the comparisons.
        This function should be used to compare models and TemplateModels in mira.
        You should use this tool if a user requests to structurally compare models, or compare them, or compare and visualize them.

        If the user does not specify which models to compare, compare the models that have currently being worked with.
        If you are unsure which models are being used, ask the user for information.

        Args:
            model_vars (list): a list of strings of the variable names for models to be compared.

        Returns:
            str: The code used to compare the models.
        """
        loop.set_state(loop.STOP_SUCCESS)
        # sometimes model_vars contains a dict and not a list despite the signature --
        # handle those cases by extracting the proper field
        if isinstance(model_vars, dict):
            model_vars = list(model_vars.get("model_vars", []))
        plot_code = agent.context.get_code(
            "compare_mira_models",
            {
                "model_vars": model_vars,
            },
        )
        result = json.dumps(
            {
                "action": "code_cell",
                "language": "python3",
                "content": plot_code.strip(),
            }
        )
        return result

    @tool(autosummarize=True)
    async def get_available_functions(self, package_name: str, agent: AgentRef):
        """
        Querying against the module or package should list all available submodules and functions that exist, so you can use this to discover available
        functions and the query the function to get usage information.
        You should ALWAYS try to run this on specific submodules, not entire libraries. For example, instead of running this on `LIBRARY_NAME` you should
        run this function on `SUBMODULE_EXAMPLE`. In fact, there should almost always be a `.` in the `package_name` argument.

        This function should be used to discover the available functions in the target library or module and get an object containing their docstrings so you can figure out how to use them.

        This function will return an object and store it into self.__functions. The object will be a dictionary with the following structure:
        {
            function_name: <function docstring>,
            ...
        }

        Read the docstrings to learn how to use the functions and which arguments they take.

        Args:
            package_name (str): this is the name of the package to get information about. For example "SUBMODULE_EXAMPLE"
        """
        functions = {}
        code = agent.context.get_code("info", {"package_name": package_name})
        info_response = await agent.context.beaker_kernel.evaluate(
            code,
            parent_header={},
        )
        with open('/tmp/info.json', 'r') as f:
            info = json.loads(f.read())
        for var_name, info in info.items():
            if var_name in functions:
                functions[var_name] = info
            else:
                functions[var_name] = info

        agent.context.functions.update(functions)

        return functions

    @tool(autosummarize=True)
    async def get_functions_and_classes_docstring(self, list_of_function_or_class_names: list, agent: AgentRef):
        """
        Use this tool to additional information on individual function or class such as their inputs, outputs and description (and generally anything else that would be in a docstring)
        You should ALWAYS use this tool before writing or checking code to check the function signatures of the functions or classes you are about to use.

        Read the information returned to learn how to use the function or class and which arguments they take.

        The function and class names used in the input to this tool should include the entire module hierarchy, ie. CLASS_EXAMPLE

        Args:
            list_of_function_or_class_names (list): this is a list of the the names of the functions and/or classes to get information about. For example ["CLASS_EXAMPLE","FUNCTION_EXAMPLE"]
        """
        # TODO: figure out cause of this and remove ugly filter
        if type(list_of_function_or_class_names) == dict:
            list_of_function_or_class_names = list_of_function_or_class_names['list_of_function_or_class_names']
        help_string = ''
        for func_or_class_name in list_of_function_or_class_names:
            module_name = func_or_class_name.rsplit('.', 1)[0]
            importlib.import_module(module_name)

            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                help(func_or_class_name)
                # Store the help text in the dictionary
                help_text = buf.getvalue()
            help_string += f'{func_or_class_name}: {help_text}'
            agent.context.functions[func_or_class_name] = help_text
        return help_string

    @tool(autosummarize=True)
    async def get_functions_and_classes_source_code(self, list_of_function_or_class_names: list, agent: AgentRef):
        """
        Use this tool to additional information on individual function or class such as their inputs, outputs and description (and generally anything else that would be in a docstring)
        You should ALWAYS use this tool before writing or checking code to check the function signatures of the functions or classes you are about to use.

        Read the information returned to learn how to use the function or class and which arguments they take.

        The function and class names used in the input to this tool should include the entire module hierarchy, ie. CLASS_EXAMPLE

        Args:
            list_of_function_or_class_names (list): this is a list of the the names of the functions and/or classes to get information about. For example ["CLASS_EXAMPLE","FUNCTION_EXAMPLE"]
        """
        # TODO: figure out cause of this and remove ugly filter
        if type(list_of_function_or_class_names) == dict:
            list_of_function_or_class_names = list_of_function_or_class_names['list_of_function_or_class_names']
        help_string = ''
        for func_or_class_name in list_of_function_or_class_names:
            module_path, object_name = func_or_class_name.rsplit('.', 1)
            module = importlib.import_module(module_path)
            obj = getattr(module, object_name)
            try:
                source_code = inspect.getsource(obj)
            except TypeError:
                source_code = inspect.getsource(module)
            # TODO: maybe use help on the object if it is an object and not a class?
            help_string += f'{func_or_class_name} source code: \n{source_code}'
            # agent.context.functions[func_or_class_name]=help_text
        return help_string

    @tool(autosummarize=True)
    async def search_documentation(self, query: str):
        """
        Use this tool to search the documentation for sections relevant to the task you are trying to perform.
        Input should be a natural language query meant to find information in the documentation as if you were searching on a search bar.
        Response will be sections of the documentation that are relevant to your query.

        Args:
            query (str): Natural language query. Some Examples - DOCUMENTATION_QUERY_EXAMPLES
        """
        from .lib.utils import query_docs

        return query_docs(query)

    @tool(autosummarize=True)
    async def search_functions_classes(self, query: str):
        """
        Use this tool to search the code in the LIBRARY_NAME repo for function and classes relevant to your query.
        Input should be a natural language query meant to find information in the documentation as if you were searching on a search bar.
        Response will be a string with the top few results, each result will have the function or class doc string and the source code (which includes the function signature)

        Args:
            query (str): Natural language query. Some Examples - DOCUMENTATION_QUERY_EXAMPLES
        """
        from .lib.utils import query_functions_classes

        return query_functions_classes(query)


class Agent(NewBaseAgent):
    """
    You are assisting us in performing important scientific tasks.

    If you don't have the details necessary, you should use the ask_user tool to ask the user for them.
    """

    def __init__(self, context: BaseContext = None, tools: list = None, **kwargs):
        tools = [Toolset]
        super().__init__(context, tools, **kwargs)
        self.context_conf = json.loads(CONTEXT_JSON)
        self.most_recent_user_query = ''
        self.checked_code = False
        self.code_attempts = 0

    @tool()
    async def submit_code(self, code: str, agent: AgentRef, loop: LoopControllerRef) -> None:
        """
        Use this when you are ready to submit your code to the user.


        Ensure to handle any required dependencies, and provide a well-documented and efficient solution. Feel free to create helper functions or classes if needed.

        Please generate the code as if you were programming inside a Jupyter Notebook and the code is to be executed inside a cell.
        You MUST wrap the code with a line containing three backticks before and after the generated code like the code below but replace the triple_backticks:

        ```
        import numpy
        ```

        No additional text is needed in the response, just the code block with the triple backticks.


        Args:
            code (str): code block to be submitted to the user inside triple backticks.
        """
        loop.set_state(loop.STOP_SUCCESS)
        try:
            preamble, code, coda = re.split("```\w*", code)
        except ValueError as e:
            print(f"error splitting code block on whitespace: {e}")
        result = json.dumps(
            {
                "action": "code_cell",
                "language": self.context.subkernel.KERNEL_NAME,
                "content": code.strip(),
            }
        )
        # check if successful then reset check code...
        return result
