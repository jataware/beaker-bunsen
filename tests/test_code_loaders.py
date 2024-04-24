import os
import pytest
from pathlib import Path

from beaker_bunsen.vectordb.types import LoadableResource
from beaker_bunsen.vectordb.loaders.code_library_loader import PythonLibraryLoader


def test_python_module_discovery():
    python_loader = PythonLibraryLoader()

    os_records = list(python_loader.discover(locations=["os"]))
    requests_records = list(python_loader.discover(locations=["requests"]))
    combined_records = list(python_loader.discover(locations=["os", "requests"]))

    requests_uris = [record.uri for record in requests_records]
    requests_locations = [uri.split(":", maxsplit=1)[1] for uri in requests_uris]
    # print(requests_uris)
    requests_files = [os.path.split(location)[1] for location in requests_locations]
    top_requests_record = requests_records[0]
    top_request_location_slug, top_requests_location = top_requests_record.uri.split(":", maxsplit=1)
    top_requests_dir, top_requests_file = os.path.split(top_requests_location)

    assert len(os_records) == 1
    assert len(requests_records) > 5  # We don't really know how many files/submodules will always make up requests, but this limit should be relatively future proof.
    assert len(os_records) + len(requests_records) == len(combined_records)
    assert os_records[0].uri.endswith('/os.py')
    assert isinstance(top_requests_record.uri, str)
    assert isinstance(top_requests_record.id, str)
    assert top_requests_record.uri
    assert top_requests_record.id
    assert '__init__.py' in requests_files
    assert top_request_location_slug == "file"
    assert os.path.isfile(top_requests_location)
    assert top_requests_dir.endswith('/requests')
    assert top_requests_file.endswith('.py')


def test_python_load():
    python_loader = PythonLibraryLoader()

    os_record = list(python_loader.discover(locations=["os"]))[0]
    uri = os_record.uri
    source = python_loader.load(uri)

    assert len(source) > 0
    assert isinstance(source, str)
    assert source.startswith('r"""OS')
    assert "\nenviron = " in source
    assert "def makedirs(" in source
