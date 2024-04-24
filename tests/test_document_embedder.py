# Use pysqlite3-bin library instead of OS pysqlite3 which may be an incompatible version
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import pytest
from pathlib import Path

from beaker_bunsen.vectordb.types import LoadableResource
from beaker_bunsen.vectordb.chromadb_store import ChromaDBLocalStore
from beaker_bunsen.vectordb.loaders.local_file_loader import LocalFileLoader
from beaker_bunsen.vectordb.embedders.documents import DocumentEmbedder

@pytest.fixture()
def chromadb_store_path(tmp_path_factory):
    return str(tmp_path_factory.mktemp("test"))


@pytest.fixture()
def test_data_paths():
    data = Path(__file__).parent / "data"
    return [data / "documents"]


def test_document_embedder(chromadb_store_path, test_data_paths):
    store = ChromaDBLocalStore(path=chromadb_store_path)
    loader = LocalFileLoader(locations=test_data_paths)
    embedder = DocumentEmbedder(
        loader=loader,
        store=store,
    )

    records_before_ingestion = store.get_all()
    embedder.ingest()
    ingested_records = store.get_all()

    assert len(records_before_ingestion) == 0
    assert len(ingested_records) > 0
