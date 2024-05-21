import contextlib
import importlib
import inspect
import io
import json
import logging
import os
import pickle
from importlib import import_module
from typing import TYPE_CHECKING, Any, Dict, List
from uuid import uuid4
from beaker_kernel.lib.subkernels.base import BaseSubkernel
import requests
import datetime

from beaker_kernel.lib.autodiscovery import LIB_LOCATIONS
from beaker_kernel.lib.context import BaseContext
from beaker_kernel.lib.subkernels.python import PythonSubkernel
from beaker_kernel.lib.utils import action

from .bunsen_agent import BunsenAgent
from .corpus import Corpus

if TYPE_CHECKING:
    from beaker_kernel.kernel import LLMKernel
    from beaker_kernel.lib.subkernels.base import BaseSubkernel


logger = logging.getLogger(__name__)


class EnvironmentSerializer:
    pass


class BunsenContext(BaseContext):
    agent_cls: BunsenAgent
    corpus: Corpus

    enabled_subkernels: list[str]
    bunsen_config: dict[str, Any] | None
    environment_serializer: EnvironmentSerializer

    def __init__(
        self,
        beaker_kernel: "LLMKernel",
        config: Dict[str, Any],
    ) -> None:
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


    async def get_context_prompt(self):
        """
        Class that can be overridden by subclassing to provide context specific prompt information in to the autoprompt
        """
        return None

    async def build_prompt(
            self,
            state: dict[str,any],
            code_examples: list[str] = None,
        ) -> str:
        if state:
            variables = state.get("variables", {})
            modules = state.get("modules", [])
            functions = state.get("functions", {})
        else:
            variables = {}
            modules = []
            functions = []


        python_libraries = self.bunsen_config.get("python_libraries", [])
        if len(python_libraries) > 1:
            python_library_str = f"Python libraries {', '.join(python_libraries)}"
        elif len(python_libraries) == 1:
            python_library_str = f"Python library {python_libraries[0]}"
        else:
            python_library_str = None
        r_cran_libraries = self.bunsen_config.get("r_cran_libraries", [])
        if len(r_cran_libraries) > 1:
            r_cran_library_str = f"r_cran libraries {', '.join(r_cran_libraries)}"
        elif len(r_cran_libraries) == 1:
            r_cran_library_str = f"r_cran library {r_cran_libraries[0]}"
        else:
            r_cran_library_str = None

        library_str = " and ".join(libs for libs in (python_library_str, r_cran_library_str) if libs)
        submodule_description = None
        code_example_str = "\n".join(
            """
======== example {num} start ========
{example}
======== example {num} end   ========
            """.strip().format(num=num, example=example)
            for num, example in enumerate(code_examples, start=1)
        )

        library_descriptions = []
        for lib in python_libraries:
            description = self.bunsen_config.get("library_descriptions", {}).get(lib, None)
            if description:
                library_descriptions.append(description.strip())

        library_description = "\n".join(library_descriptions)

        # TODO: Make this nice once we have more submodule info available
        if submodule_description:
            submodule_info = f"""
Below is some information on the submodules in {library_str}:

{submodule_description}
"""
        else:
            submodule_info = ""

        self.beaker_kernel.debug("bunsen_prompt", self.bunsen_config)
        self.beaker_kernel.debug("bunsen_prompt", library_descriptions)
        self.beaker_kernel.debug("bunsen_prompt", library_str)
        intro = f"""You are an exceptionally intelligent coding assistant that consistently delivers accurate and reliable responses to user instructions.
{library_description}

You should ALWAYS try looking up the what the user is asking you to do or portions of what the user is asking you to do in the documentation to get a sense of how it can be done.
You should ALWAYS think about which functions and classes from {library_str} you are going to use before you write code. Try to use {library_str} as much as possible.
You can do so in the following ways:
If the functions you want to use are in the context below, no need to look them up again.
Otherwise, first try to use the Toolset.search_functions_classes to search for relevant functions and classes.
If that does not provide enough information, lookup the available functions for related modules using Toolset.get_available_functions.
If there is a main class or function you are using, you can lookup all the information on it and all the objects and functions required to use it using Toolset.get_class_or_function_full_information.
Use this when you want to instantiate a complicated object.

You can lookup source code for individual functions or classes using the `get_source_code` tool before using a function from {library_str}.
{submodule_info}

Additionally here are some similar examples of similar user requests and your previous successful code generations.
If the request from the user is similar enough to one of these examples, use it to help write code to answer the user's request.

{code_example_str or 'No examples provided.'}
"""

        # """If there is a main class or function you are using, you can lookup all the information on it and all the objects and functions required to use it using Toolset.get_class_or_function_full_information.
        # Use this when you want to instantiate a complicated object."""


        code_environment = f"""These are the variables in the user's current code environment with key value pairs:
{variables}

The user has also imported the following modules: {','.join(modules)}. So you don't need to import them when generating code.
When writing code that edits the variables that the user has in their environment be sure to modify them in place.
For example if we have a variable a=1, if we wanted to change a to 2, we you write a=2.
When the user asks you to perform an action, if they specifically mention a variable name, be sure to use that variable.
Additionally if the object they ask you to update is similar to an object in the code environment, be sure to use that variable.
"""

        outro = f"""
Please answer any user queries or perform user instructions to the best of your ability, but do not guess if you are not sure of an answer.
"""

        context = await self.get_context_prompt()

        parts = []
        parts.append(intro)
        parts.append(code_environment)
        if context:
            parts.append(context)
        parts.append(outro)
        result = "\n".join(parts)

        self.beaker_kernel.debug("bunsen_prompt", result)
        return result


    async def auto_context(self):
        state = await self.get_subkernel_state()
        # most_recent_user_query = ""
        for message in reversed(self.agent.messages):
            if message["role"] == "user":
                most_recent_user_query = message["content"]
                break
        else:
            most_recent_user_query = ""

        if most_recent_user_query:
            code_examples = [
                result["record"].content
                for result in self.corpus.store.query(
                    most_recent_user_query,
                    partition="examples",
                    limit=5,
                )["matches"]
            ]
        else:
            code_examples = []

        prompt = await self.build_prompt(state, code_examples)

        return prompt
        # if most_recent_user_query != self.agent.most_recent_user_query:
        #     self.few_shot_examples = query_examples(most_recent_user_query)
        #     self.agent.debug(
        #         event_type="few_shot_examples",
        #         content={"few_shot_examples": self.few_shot_examples, "user_query": most_recent_user_query},
        #     )
