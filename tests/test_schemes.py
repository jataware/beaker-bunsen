import os
import pytest
import zipfile
from pathlib import Path

from beaker_bunsen.vectordb.loaders.schemes import (
    read_from_uri,
    LocalFileScheme, PythonModuleScheme, ZipfileScheme, CorpusResourceScheme,
)
from beaker_bunsen.corpus import Corpus


@pytest.fixture()
def test_data_path():
    return Path(__file__).parent / "data"


def test_localfile_scheme(test_data_path):
    file_path = test_data_path / "documents" / "yorkshire.txt"
    abs_path = file_path.absolute()
    uri = f"file://{abs_path}"

    content  = LocalFileScheme.read(uri)

    assert uri.startswith("file:///")
    assert isinstance(content, str)
    assert "Yorkshire Day is observed annually on 1 August" in content


def test_localfile_binary(test_data_path):
    file_path = test_data_path / "images" / "kitten_hacker.jpg"
    abs_path = file_path.absolute()
    uri = f"file://{abs_path}"

    content  = LocalFileScheme.read(uri)

    assert isinstance(content, bytes)
    assert len(content) == 417493


def test_pythonmod_scheme(test_data_path):

    uri = f"py-mod:uri_template.charset"

    content  = PythonModuleScheme.read(uri)

    assert "class Charset:" in content


def test_read_from_uri(test_data_path):
    docfile_path = test_data_path / "documents" / "yorkshire.txt"
    docfile_abs_path = docfile_path.absolute()
    docfile_uri = f"file://{docfile_abs_path}"

    binfile_path = test_data_path / "images" / "kitten_hacker.jpg"
    binfile_abs_path = binfile_path.absolute()
    binfile_uri = f"file://{binfile_abs_path}"

    pymod_uri = f"py-mod:uri_template.charset"

    docfile_content = read_from_uri(docfile_uri)
    binfile_content = read_from_uri(binfile_uri)
    pymod_content = read_from_uri(pymod_uri)

    assert len(docfile_content) > 0
    assert len(binfile_content) > 0
    assert len(pymod_content) > 0

    assert isinstance(docfile_content, str)
    assert isinstance(binfile_content, bytes)
    assert isinstance(pymod_content, str)


def test_load_from_local_with_basedir(test_data_path):

    uri = "file:documents/yorkshire.txt"

    content_direct = LocalFileScheme.read(uri, base_dir=str(test_data_path))
    content_read_from_uri = read_from_uri(uri, base_dir=str(test_data_path))

    assert isinstance(content_direct, str)
    assert isinstance(content_read_from_uri, str)
    assert "Yorkshire Day is observed annually on 1 August" in content_direct
    assert "Yorkshire Day is observed annually on 1 August" in content_read_from_uri



def test_load_from_zipped_file(test_data_path):
    zipfile_path = test_data_path / "corpuses" / "corpus.zip"
    file_from_zipfile = Path("resources/code/requests.adapters")

    zipfile_uri = ZipfileScheme.get_uri_for_location(location=str(file_from_zipfile), base=str(zipfile_path))
    innercontent = read_from_uri(zipfile_uri)

    assert len(zipfile_uri) > 0
    assert len(innercontent) > 0
    assert zipfile_uri.startswith(ZipfileScheme.URI_SCHEME)
    assert "This module contains the transport adapters that Requests uses" in innercontent


def test_load_resource_from_corpus_dir(test_data_path):
    corpus_path = test_data_path / "corpuses" / "test-corpus"
    resource_from_corpus = Path("code/requests.adapters")

    corpus_uri = CorpusResourceScheme.get_uri_for_location(location=str(resource_from_corpus))
    corpus = Corpus.from_dir(corpus_path)

    innercontent = read_from_uri(corpus_uri, corpus=corpus)
    with open(corpus_path / "resources" / resource_from_corpus) as resource_file:
        rawcontent = resource_file.read()

    # Assert that this call fails when a corpus is not provided
    with pytest.raises(TypeError):
        innercontent = read_from_uri(corpus_uri)
    assert len(corpus_uri) > 0
    assert len(innercontent) > 0
    assert corpus_uri.startswith(CorpusResourceScheme.URI_SCHEME)
    assert "This module contains the transport adapters that Requests uses" in innercontent
    assert innercontent == rawcontent
