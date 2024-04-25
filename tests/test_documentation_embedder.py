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
from beaker_bunsen.vectordb.embedders.documentation import DocumentationEmbedder


@pytest.fixture()
def chromadb_store_path(tmp_path_factory):
    return str(tmp_path_factory.mktemp("test"))

@pytest.fixture()
def test_data_path():
    data = Path(__file__).parent / "data"
    return data / "documentation"

@pytest.fixture()
def test_data_paths(test_data_path):
    return [test_data_path]


def test_document_splitting(chromadb_store_path, test_data_path):
    # Only load the first file in the documentation directory
    filename = str(test_data_path / (os.listdir(test_data_path))[0])
    loader = LocalFileLoader(locations=[filename])
    store = ChromaDBLocalStore(path=chromadb_store_path)
    embedder = DocumentationEmbedder(loader=loader, store=store)

    embedder.ingest()

    ingested_records = sorted(store.get_all(), key=lambda record: record.id)
    first_record, second_record = ingested_records[:2]
    record_ids = sorted(record.id for record in ingested_records)

    assert len(ingested_records) > 1
    assert first_record.content[-40:] in second_record.content[:200]  # Assert overlap feature is working
    assert first_record.uri == f"file:{filename}"
    with open(filename) as rawfile:
        raw_data = rawfile.read()
        for record in ingested_records:
            assert record.content in raw_data
        assert raw_data.startswith(first_record.content)
    assert record_ids[0].endswith(f"{filename}:1")


def test_document_embedder(chromadb_store_path, test_data_paths):
    store = ChromaDBLocalStore(path=chromadb_store_path)
    loader = LocalFileLoader(locations=test_data_paths)
    embedder = DocumentationEmbedder(
        loader=loader,
        store=store,
    )

    records_before_ingestion = store.get_all()
    embedder.ingest()
    ingested_records = store.get_all()
    record_ids = set(record.id for record in ingested_records)
    record_uris = set(record.uri for record in ingested_records)


    assert len(records_before_ingestion) == 0
    assert len(ingested_records) > 0
    assert len(ingested_records) == len(record_ids)
    assert len(ingested_records) > len(record_uris)
