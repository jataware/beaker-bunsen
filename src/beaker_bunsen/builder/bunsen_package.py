import importlib
import inspect
import json
import logging
import os.path
import pathlib
import pkgutil
import shutil
import sys
from copy import deepcopy
from typing import Any, Callable

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.plugin import hookimpl

from beaker_kernel.lib.context import BaseContext


logger = logging.getLogger("bunsen_build")


class BuildError(Exception):
    pass


class BunsenPackageHook(BuildHookInterface):
    PLUGIN_NAME = "bunsen_package"
    _BUILD_DIR = "build"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:

        if os.path.exists(self._BUILD_DIR):
           shutil.rmtree(self._BUILD_DIR)
        os.makedirs(self._BUILD_DIR)

        if "shared-data" not in build_data:
            build_data["shared_data"] = {}

        if self.target_name == "wheel":
            # Register Beaker subcommand
            # TODO: Move this to be a function in beaker for consistency?
            subcommand_hook = {
                "group_name": "bunsen",
                "module": "beaker_bunsen.scripts.bunsen",
                "entry_point": "cli_commands",
            }
            subcommand_hook_path = os.path.join(self._BUILD_DIR, f"subcommand_hook.json")
            with open(subcommand_hook_path, 'w') as subcommand_hook_file:
                json.dump(subcommand_hook, subcommand_hook_file, indent=2)

            build_data["shared_data"][subcommand_hook_path] = f"share/beaker/commands/beaker_bunsen.json"


@hookimpl
def hatch_register_build_hook():
    return BunsenPackageHook
