import contextlib
import importlib
import importlib.util
import logging
import os
import pkgutil
import requests
import sys
import tarfile
import tempfile
from collections import deque, defaultdict
from pathlib import Path
from typing import Any

from .base import BaseLoader
from .schemes import SQLiteScheme, read_from_uri
from .sqlite_loader import SQLiteLoader
from ..types import Default, DefaultType, URI
from ..resources import CodeResource, ExampleResource, DocumentationResource, ResourceFilter

logger = logging.getLogger("beaker_bunsen")


class SkillLoader(SQLiteLoader):

    Scheme = SQLiteScheme
    SLUG = "skill"

    def discover(
        self,
        locations: list[str] | DefaultType = Default,
        metadata: dict | DefaultType = Default,
        exclusions: list[str] | DefaultType = Default,
        filter: ResourceFilter | DefaultType = Default,
    ):
        pass
