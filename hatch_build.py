"""Custom hatch build hook"""
import ast
import importlib
import inspect
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


# TODO: Figure out how to make a Bunsen Hook and allow it to be used in subclasses
class CustomHook(BuildHookInterface):
    """The IPykernel build hook."""

    def initialize(self, version, build_data):
        """Initialize the hook."""
        pass

