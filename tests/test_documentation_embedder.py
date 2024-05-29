import os
import pytest
from pathlib import Path

from beaker_bunsen.corpus.vector_stores.chromadb_store import ChromaDBLocalStore
from beaker_bunsen.corpus.corpus import Corpus
from beaker_bunsen.corpus.types import URI


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
    fileuri = URI(f"documentation:{test_data_path / (os.listdir(test_data_path))[0]}")
    store = ChromaDBLocalStore(path=chromadb_store_path)
    corpus = Corpus(store)
    corpus.ingest(
        locations=[fileuri],
        chunk_size=400,
        chunk_overlap=80,
    )

    ingested_records = sorted(store.get_all(partition="documentation"), key=lambda record: record.id)
    first_record, second_record = ingested_records[:2]
    record_ids = sorted(record.id for record in ingested_records)

    assert len(ingested_records) > 1
    # Due to change in chunking, overlap is no longer assured.
    # assert first_record.content[-20:] in second_record.content[:400]  # Assert overlap feature is working

    assert first_record.uri.path == fileuri.path
    with open(fileuri.path) as rawfile:
        raw_data = rawfile.read()
        for record in ingested_records:
            assert record.content in raw_data
        assert raw_data.startswith(first_record.content)
    assert record_ids[0].endswith(f"{fileuri.path}:1")


def test_document_embedder(chromadb_store_path, test_data_paths):
    store = ChromaDBLocalStore(path=chromadb_store_path)
    locations = [f"file:{path}" for path in test_data_paths]
    corpus = Corpus(store)

    records_before_ingestion = store.get_all()
    corpus.ingest(locations=locations)

    ingested_records = store.get_all()
    record_ids = set(record.id for record in ingested_records)
    record_uris = set(record.uri for record in ingested_records)


    assert len(records_before_ingestion) == 0
    assert len(ingested_records) > 0
    assert len(ingested_records) == len(record_ids)
    assert len(ingested_records) > len(record_uris)
