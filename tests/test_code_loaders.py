import os
import pytest
from pathlib import Path
from urllib.parse import urlparse

from beaker_bunsen.vectordb.types import Resource
from beaker_bunsen.vectordb.loaders.code_library_loader import PythonLibraryLoader


def test_python_module_discovery():
    python_loader = PythonLibraryLoader()

    os_records = list(python_loader.discover(locations=["os"]))
    requests_records = list(python_loader.discover(locations=["requests"]))
    combined_records = list(python_loader.discover(locations=["os", "requests"]))

    requests_uris = [record.uri for record in requests_records]
    requests_schemes = [urlparse(uri).scheme for uri in requests_uris]
    requests_modules = [urlparse(uri).path for uri in requests_uris]
    top_requests_record = requests_records[0]

    assert len(os_records) == 1
    assert len(requests_records) > 5  # We don't really know how many files/submodules will always make up requests, but this limit should be relatively future proof.
    assert len(os_records) + len(requests_records) == len(combined_records)
    assert os_records[0].uri == 'py-mod:os'
    assert isinstance(top_requests_record.uri, str)
    assert isinstance(top_requests_record.id, str)
    assert top_requests_record.uri
    assert top_requests_record.id
    assert 'requests.adapters' in requests_modules
    assert all([scheme == "py-mod" for scheme in requests_schemes])
    assert all([module.startswith("requests") for module in requests_modules])


def test_python_load():
    python_loader = PythonLibraryLoader()

    os_record = list(python_loader.discover(locations=["os"]))[0]
    uri = os_record.uri
    source = python_loader.read(uri)

    assert len(source) > 0
    assert isinstance(source, str)
    assert source.startswith('r"""OS')
    assert "\nenviron = " in source
    assert "def makedirs(" in source
