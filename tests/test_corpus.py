# Use pysqlite3-bin library instead of OS pysqlite3 which may be an incompatible version
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import pytest
from pathlib import Path

from beaker_bunsen.vectordb.types import Resource
from beaker_bunsen.vectordb.chromadb_store import BaseChromaDBStore, ZippedChromaDBStore
from beaker_bunsen.vectordb.embedders import BaseEmbedder, DocumentationEmbedder, ExampleEmbedder
from beaker_bunsen.vectordb.loaders import LocalFileLoader, PythonLibraryLoader
from beaker_bunsen.corpus import Corpus

def get_all_records_by_partition(store: BaseChromaDBStore):
    return sorted(
        ((partition, sorted(store.get_all(partition=partition), key=lambda p:p.id))
        for partition in store.get_partitions())
    )

@pytest.fixture()
def test_temp_path(tmp_path_factory):
    return Path(tmp_path_factory.mktemp("test"))

@pytest.fixture()
def chromadb_store_path(tmp_path_factory):
    return str(tmp_path_factory.mktemp("test"))

@pytest.fixture()
def test_data_path():
    return Path(__file__).parent / "data"


def test_corpus_ingest(test_temp_path, test_data_path):
    zip_location = test_temp_path / "store.zip"
    store = ZippedChromaDBStore(path=zip_location)

    corpus = Corpus(store=store)
    corpus_records_1 = get_all_records_by_partition(corpus.store)

    # example_embedder = DocumentationEmbedder
    example_loader = LocalFileLoader(locations=[test_data_path / "documentation"])
    corpus.ingest(embedder_cls=DocumentationEmbedder, loader=example_loader, partition="documentation")
    corpus_records_2 = get_all_records_by_partition(corpus.store)

    mira_loader = PythonLibraryLoader(locations=["mira"])
    corpus.ingest(embedder_cls=DocumentationEmbedder, loader=mira_loader, partition="code")

    corpus_records_3 = get_all_records_by_partition(corpus.store)
    print({
        k: len(v)
        for k, v in get_all_records_by_partition(corpus.store)
    })

    assert len(corpus_records_1) == 0
    assert len(corpus_records_2) > len(corpus_records_1)
    assert len(corpus_records_3) > len(corpus_records_2)



# def test_corpus_save():
#     pass


# def test_corpus_load():
#     pass


# def test_corpus_query():
#     pass
