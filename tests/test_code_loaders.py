import os
import pytest
from packaging.version import Version
from pathlib import Path
from urllib.parse import urlparse

from beaker_bunsen.corpus.resources import Resource
from beaker_bunsen.corpus.loaders.code_library_loader import PythonLibraryLoader, RCRANSourceLoader, RCRANLocalCache


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


def test_exclusions_init():
    excluded_python_loader = PythonLibraryLoader(locations=["requests", "!requests._internal_utils", "!__version__"])
    excluded_requests_records = list(excluded_python_loader.discover())
    full_python_loader = PythonLibraryLoader(locations=["requests"])
    full_requests_records = list(full_python_loader.discover())

    excluded_record_uris = [record.uri for record in excluded_requests_records]
    full_record_uris = [record.uri for record in full_requests_records]

    assert 'py-mod:requests._internal_utils' in full_record_uris
    assert 'py-mod:requests.__version__' in full_record_uris
    assert 'py-mod:requests._internal_utils' not in excluded_record_uris
    assert 'py-mod:requests.__version__' not in excluded_record_uris

    assert set(full_record_uris) - set(excluded_record_uris) == set(['py-mod:requests._internal_utils', 'py-mod:requests.__version__'])


def test_exclusions_discover():
    excluded_python_loader = PythonLibraryLoader()
    excluded_requests_records = list(excluded_python_loader.discover(locations=["requests", "!requests._internal_utils", "!__version__"]))
    full_python_loader = PythonLibraryLoader()
    full_requests_records = list(full_python_loader.discover(locations=["requests"]))

    excluded_record_uris = [record.uri for record in excluded_requests_records]
    full_record_uris = [record.uri for record in full_requests_records]

    assert 'py-mod:requests._internal_utils' in full_record_uris
    assert 'py-mod:requests.__version__' in full_record_uris
    assert 'py-mod:requests._internal_utils' not in excluded_record_uris
    assert 'py-mod:requests.__version__' not in excluded_record_uris

    assert set(full_record_uris) - set(excluded_record_uris) == set(['py-mod:requests._internal_utils', 'py-mod:requests.__version__'])


def test_exclusions_base_exclusions():
    excluded_python_loader = PythonLibraryLoader(exclusions=["__version__"])
    excluded_requests_records = list(excluded_python_loader.discover(locations=["requests", "!requests._internal_utils"]))
    full_python_loader = PythonLibraryLoader()
    full_requests_records = list(full_python_loader.discover(locations=["requests"]))

    excluded_record_uris = [record.uri for record in excluded_requests_records]
    full_record_uris = [record.uri for record in full_requests_records]

    assert 'py-mod:requests._internal_utils' in full_record_uris
    assert 'py-mod:requests.__version__' in full_record_uris
    assert 'py-mod:requests._internal_utils' not in excluded_record_uris
    assert 'py-mod:requests.__version__' not in excluded_record_uris

    assert set(full_record_uris) - set(excluded_record_uris) == set(['py-mod:requests._internal_utils', 'py-mod:requests.__version__'])


def test_r_cran_source_loader():
    loader = RCRANSourceLoader()

    resources = list(loader.discover(locations=["leaflet"]))

    # TODO: More testing

    assert len(RCRANLocalCache.remote_package_cache) > 0
    assert "leaflet" in RCRANLocalCache.remote_package_cache
    assert Version(RCRANLocalCache.remote_package_cache["leaflet"]["version"]) > Version("2.0")
    assert len(resources) > 0
