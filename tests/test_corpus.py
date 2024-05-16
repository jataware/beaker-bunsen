import os
import pytest
import zipfile
from pathlib import Path

from beaker_bunsen.vectordb.types import Resource
from beaker_bunsen.vectordb.chromadb_store import BaseChromaDBStore, ZippedChromaDBStore
from beaker_bunsen.vectordb.embedders import BaseEmbedder, DocumentationEmbedder, ExampleEmbedder, CodeEmbedder
from beaker_bunsen.vectordb.loaders import LocalFileLoader, PythonLibraryLoader
from beaker_bunsen.vectordb.loaders.schemes import read_from_uri
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

    requests_loader = PythonLibraryLoader(locations=["requests"])
    corpus.ingest(embedder_cls=CodeEmbedder, loader=requests_loader, partition="code")

    corpus_records_3 = get_all_records_by_partition(corpus.store)

    assert len(corpus_records_1) == 0
    assert len(corpus_records_2) > len(corpus_records_1)
    assert len(corpus_records_3) > len(corpus_records_2)



def test_corpus_save_dir(test_temp_path, test_data_path):
    zip_location = test_temp_path / "store.zip"
    save_location = test_temp_path / "corpus"
    store = ZippedChromaDBStore(path=zip_location)

    corpus = Corpus(store=store)

    # example_embedder = DocumentationEmbedder
    example_loader = LocalFileLoader(locations=[test_data_path / "documentation"])
    corpus.ingest(embedder_cls=DocumentationEmbedder, loader=example_loader, partition="documentation")

    requests_loader = PythonLibraryLoader(locations=["requests"])
    corpus.ingest(embedder_cls=CodeEmbedder, loader=requests_loader, partition="code")

    corpus.save_to_dir(save_dir=save_location)

    corpus_files = list((
        str(Path(dir_path).relative_to(save_location) /  file)
        for dir_path, _, files in os.walk(save_location)
        for file in files
    ))

    assert len(corpus_files) > 0
    assert "store.zip" in corpus_files
    assert "config.yaml" in corpus_files
    assert "resources/code/requests" in corpus_files
    assert "resources/code/requests.api" in corpus_files


def test_corpus_save_zip(test_temp_path, test_data_path):
    store_zip_location = test_temp_path / "store.zip"
    save_location = test_temp_path / "corpus.zip"
    store = ZippedChromaDBStore(path=store_zip_location)

    corpus = Corpus(store=store)

    # example_embedder = DocumentationEmbedder
    example_loader = LocalFileLoader(locations=[test_data_path / "documentation"])
    corpus.ingest(embedder_cls=DocumentationEmbedder, loader=example_loader, partition="documentation")

    requests_loader = PythonLibraryLoader(locations=["requests"])
    corpus.ingest(embedder_cls=DocumentationEmbedder, loader=requests_loader, partition="code")

    corpus.save_to_zip(save_location)

    with zipfile.ZipFile(save_location) as corpus_zip:
        zipfile_contents = [z.filename for z in corpus_zip.filelist]

    assert save_location.is_file() == True
    temp_test_dir_files = list((file for _, _, files in os.walk(test_temp_path) for file in files))
    assert "corpus.zip" in temp_test_dir_files
    assert "store.zip" in zipfile_contents
    assert "config.yaml" in zipfile_contents
    assert "resources/code/requests" in zipfile_contents
    assert "resources/code/requests.api" in zipfile_contents


def test_corpus_load_dir(test_data_path):
    corpus_path = test_data_path / "corpuses" / "test-corpus"
    corpus = Corpus.from_dir(corpus_path)

    record_count_by_store = {
        k: len(v)
        for k, v in get_all_records_by_partition(corpus.store)
    }
    documentation_uris = list(set(record.uri for record in corpus.store.get_all(partition="documentation")))
    # first_doc_uri = documentation_uris[0]
    mathjax_uri = [uri for uri in documentation_uris if "mathjax" in uri][0]

    assert record_count_by_store["code"] == 33
    assert record_count_by_store["documentation"] == 6
    assert len(documentation_uris) == 2

    print(mathjax_uri)
    assert mathjax_uri.startswith("corpus:")
    assert "Beautiful math in all browsers" in read_from_uri(mathjax_uri, corpus=corpus)



def test_corpus_load_zip():
    pass


# def test_corpus_query():
#     pass
