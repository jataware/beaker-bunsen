# Use pysqlite3-bin library instead of OS pysqlite3 which may be an incompatible version
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import pytest
from pathlib import Path

from beaker_bunsen.vectordb.types import Resource
from beaker_bunsen.vectordb.chromadb_store import ChromaDBLocalStore
from beaker_bunsen.vectordb.embedders.base import BaseEmbedder
from beaker_bunsen.vectordb.loaders.local_file_loader import LocalFileLoader
from beaker_bunsen.vectordb.embedders.documentation import DocumentationEmbedder

@pytest.fixture()
def chromadb_store_path(tmp_path_factory):
    return str(tmp_path_factory.mktemp("test"))


@pytest.fixture()
def test_data_paths():
    data = Path(__file__).parent / "data"
    return [data / "documents", data / "examples"]
