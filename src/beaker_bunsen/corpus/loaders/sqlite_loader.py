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
from ..types import Default, DefaultType, URI
from ..resources import CodeResource, ExampleResource, DocumentationResource, ResourceFilter

logger = logging.getLogger("beaker_bunsen")

class SQLiteLoader(BaseLoader):

    Scheme = SQLiteScheme

    def read(
            self,
            location: str,
            base: str = ""
        ):
        if location.startswith(self.Scheme.URI_SCHEME):
            uri = location
        else:
            uri = self.Scheme.get_uri_for_location(location, base)
        return read_from_uri(uri)
