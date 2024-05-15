import os
import pytest
from pathlib import Path

from beaker_bunsen.vectordb.types import Resource
from beaker_bunsen.vectordb.loaders.local_file_loader import LocalFileLoader
from beaker_bunsen.vectordb.loaders.schemes import LocalFileScheme


@pytest.fixture()
def test_data_path():
    return Path(__file__).parent / "data"


def test_local_file_discovery(test_data_path):
    local_file_loader = LocalFileLoader()
    roots = [test_data_path / "documents", test_data_path / "images"]
    found_locations = set([record.uri for record in local_file_loader.discover(locations=roots)])
    # Strip off any `{prefix}:` from the locations
    found_files = set([location.split(":", maxsplit=1)[1] for location in found_locations])

    files_from_os_walk = set()
    for root in roots:
        for path, _, files in os.walk(root, ):
            files_from_os_walk.update([os.path.join(path, f) for f in files if not f.endswith('.metadata')])

    assert found_files == files_from_os_walk


def test_local_file_record(test_data_path):
    local_file_loader = LocalFileLoader()
    roots = [test_data_path / "documents"]
    records = list(local_file_loader.discover(locations=roots))
    uris = [record.uri for record in records]
    ids = [record.id for record in records]

    assert all([uri.startswith("file:") for uri in uris])
    assert all([id.startswith("local:") for id in ids])


def test_local_file_metadata(test_data_path):
    local_file_loader = LocalFileLoader()
    roots = [test_data_path]
    basic_metadata_map = {os.path.basename(record.uri): record.metadata for record in local_file_loader.discover(locations=roots)}
    metadata_map_with_base = {os.path.basename(record.uri): record.metadata for record in local_file_loader.discover(locations=roots, metadata={"source": "test", "extra": "base"})}

    assert basic_metadata_map["mathjax_readme.md"] == {}
    assert metadata_map_with_base["mathjax_readme.md"] == {"source": "test", "extra": "base"}

    assert basic_metadata_map["yorkshire.txt"] == {"source": "wikipedia", "url": "https://en.wikipedia.org/wiki/Yorkshire"}
    assert metadata_map_with_base["yorkshire.txt"] == {"source": "wikipedia", "url": "https://en.wikipedia.org/wiki/Yorkshire", "extra": "base"}

    assert basic_metadata_map["irish_potato_caserole"].get("source", None) is None
    assert basic_metadata_map["irish_potato_caserole"]["collection"] == "recipe"
    assert basic_metadata_map["irish_potato_caserole"].get("extra", None) is None
    assert metadata_map_with_base["irish_potato_caserole"]["source"] == "test"
    assert metadata_map_with_base["irish_potato_caserole"]["collection"] == "recipe"
    assert metadata_map_with_base["irish_potato_caserole"]["extra"] == "base"

    assert basic_metadata_map["winter_risotto"]["source"] == "https://publicdomainrecipes.com/winter-risotto/"
    assert basic_metadata_map["winter_risotto"]["collection"] == "recipe"
    assert basic_metadata_map["winter_risotto"].get("extra", None) is None
    assert basic_metadata_map["winter_risotto"]["contributors"] == "Joel Maxuel"
    assert metadata_map_with_base["winter_risotto"]["source"] == "https://publicdomainrecipes.com/winter-risotto/"
    assert metadata_map_with_base["winter_risotto"]["collection"] == "recipe"
    assert metadata_map_with_base["winter_risotto"]["extra"] == "base"
    assert metadata_map_with_base["winter_risotto"]["contributors"] == "Joel Maxuel"


def test_load_abs_local_file_w_scheme():
    local_file_loader = LocalFileLoader()
    abs_file_path = Path(__file__).parent / "data" / "documents" / "yorkshire.txt"
    file_uri = LocalFileScheme.get_uri_for_location(abs_file_path)
    data = local_file_loader.read(file_uri)

    assert len(data) > 0
    assert isinstance(data, str)
    assert data.startswith("Yorkshire")
    assert data.endswith("Yorkshire Rugby Football Union.\n")

def test_load_abs_local_file_wo_scheme():
    local_file_loader = LocalFileLoader()
    abs_file_path = Path(__file__).parent / "data" / "documents" / "yorkshire.txt"
    data = local_file_loader.read(str(abs_file_path))

    assert len(data) > 0
    assert isinstance(data, str)
    assert data.startswith("Yorkshire")
    assert data.endswith("Yorkshire Rugby Football Union.\n")

def test_load_relative_local_file():
    local_file_loader = LocalFileLoader()
    base = Path(__file__).parent
    relative_path =  Path("data") / "documents" / "yorkshire.txt"
    data = local_file_loader.read(str(relative_path), base=str(base))

    assert len(data) > 0
    assert isinstance(data, str)
    assert data.startswith("Yorkshire")
    assert data.endswith("Yorkshire Rugby Football Union.\n")

def test_exclusions_init():
    exclusion = "ato"
    abs_file_path = Path(__file__).parent / "data" / "documents"
    local_file_loader = LocalFileLoader(
        locations=[abs_file_path],
        exclusions=[exclusion],
    )
    found_locations = set([record.uri for record in local_file_loader.discover()])
    # Strip off any `{prefix}:` from the locations
    found_files = set([location.split(":", maxsplit=1)[1] for location in found_locations])

    files_from_os_walk = set()
    for path, _, files in os.walk(abs_file_path, ):
        files_from_os_walk.update([os.path.join(path, f) for f in files if not f.endswith('.metadata')])

    excluded_files = files_from_os_walk - found_files

    assert len(found_files) < len(files_from_os_walk)
    assert any([exclusion in filename for filename in files_from_os_walk])
    assert all([exclusion in filename for filename in excluded_files])
    assert all([exclusion not in filename for filename in found_files])

def test_exclusions_discover():
    exclusion = "ato"
    abs_file_path = Path(__file__).parent / "data" / "documents"
    local_file_loader = LocalFileLoader()
    found_locations = set([record.uri for record in local_file_loader.discover(
        locations=[abs_file_path, f"!{exclusion}"],
    )])
    # Strip off any `{prefix}:` from the locations
    found_files = set([location.split(":", maxsplit=1)[1] for location in found_locations])

    files_from_os_walk = set()
    for path, _, files in os.walk(abs_file_path, ):
        files_from_os_walk.update([os.path.join(path, f) for f in files if not f.endswith('.metadata')])

    excluded_files = files_from_os_walk - found_files

    assert len(found_files) < len(files_from_os_walk)
    assert any([exclusion in filename for filename in files_from_os_walk])
    assert all([exclusion in filename for filename in excluded_files])
    assert all([exclusion not in filename for filename in found_files])
