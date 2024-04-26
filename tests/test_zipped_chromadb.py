# Use pysqlite3-bin library instead of OS pysqlite3 which may be an incompatible version
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import pytest
import shutil
from pathlib import Path

from beaker_bunsen.vectordb.chromadb_store import ChromaDBLocalStore, Record, ZippedChromaDBStore

@pytest.fixture()
def chromadb_store(test_temp_path):
    store_path = str(Path(test_temp_path) / "store")
    store = ChromaDBLocalStore(path=store_path, settings={'default_partition': "testing"})
    return store

@pytest.fixture()
def test_data_path():
    return Path(__file__).parent.absolute() / "data"

@pytest.fixture()
def test_temp_path(tmp_path_factory):
    return Path(tmp_path_factory.mktemp("test"))


def test_creation(test_temp_path):
    zip_location = test_temp_path / "store.zip"
    zipped_store = ZippedChromaDBStore(path=zip_location)

    assert isinstance(zipped_store, ZippedChromaDBStore)
    assert os.path.exists(zipped_store.tempdir)
    assert os.path.exists(os.path.join(zipped_store.tempdir, "store"))


def test_population_and_query(test_temp_path, test_data_path):
    zip_location = test_temp_path / "store.zip"
    zipped_store = ZippedChromaDBStore(path=zip_location)

    bundle = [
        Record(
            id='test2',
            content="What is past is prologue.",
            metadata={'source': 'The Tempest'}
        ),
        Record(
            id='test3',
            content="It is the east, and Juliet the sun.",
        ),
        Record(
            id='test4',
            content="I knew him, Horatio",
            metadata={'source': 'Hamlet'}
        ),
        Record(
            id='test5',
            content="Neither a borrower, nor a lender be.",
        ),
    ]

    zipped_store.add_records(bundle)
    results = zipped_store.query("Hamlet")
    top_result = results["matches"][0]["record"]

    assert len(results["matches"]) == 4
    assert top_result.id == 'test4'


def test_from_localstore(test_temp_path, test_data_path, chromadb_store):

    bundle = [
        Record(
            id='test2',
            content="What is past is prologue.",
            metadata={'source': 'The Tempest'}
        ),
        Record(
            id='test3',
            content="It is the east, and Juliet the sun.",
        ),
        Record(
            id='test4',
            content="I knew him, Horatio",
            metadata={'source': 'Hamlet'}
        ),
        Record(
            id='test5',
            content="Neither a borrower, nor a lender be.",
        ),
    ]

    chromadb_store.add_records(bundle)

    zip_location = test_temp_path / "store.zip"
    zipped_store = ZippedChromaDBStore.from_localstore(localstore=chromadb_store, zipfile=zip_location)

    results = zipped_store.query("Hamlet")
    top_result = results["matches"][0]["record"]

    assert len(results["matches"]) == 4
    assert top_result.id == 'test4'


def test_saving(test_temp_path):
    zip_location = test_temp_path / "store.zip"
    zipped_store = ZippedChromaDBStore(path=zip_location)

    bundle = [
        Record(
            id='test2',
            content="What is past is prologue.",
            metadata={'source': 'The Tempest'}
        ),
        Record(
            id='test3',
            content="It is the east, and Juliet the sun.",
        ),
        Record(
            id='test4',
            content="I knew him, Horatio",
            metadata={'source': 'Hamlet'}
        ),
        Record(
            id='test5',
            content="Neither a borrower, nor a lender be.",
        ),
    ]

    zipped_store.add_records(bundle)

    zipfile_exists_before_update = os.path.isfile(zip_location)
    zipped_store.update_zipfile()
    zipfile_exists_after_update = os.path.isfile(zip_location)


    assert zipfile_exists_before_update == False
    assert zipfile_exists_after_update == True
    assert os.path.getsize(zip_location) > 0
    with open(zip_location, 'rb') as zipfile_fh:
        magic = zipfile_fh.read(4)
    assert magic == b'\x50\x4b\03\x04'  # Magic signature for zip files -- https://en.wikipedia.org/wiki/List_of_file_signatures


def test_load_zipped_store(test_data_path):
    zip_location = test_data_path / "store.zip"
    zipfile_exists_before_init = os.path.isfile(zip_location)
    zipped_store = ZippedChromaDBStore(path=zip_location)

    results = zipped_store.query("Hamlet")
    top_result = results["matches"][0]["record"]

    assert zipfile_exists_before_init == True
    assert len(results["matches"]) == 4
    assert top_result.id == "test4"

@pytest.mark.filterwarnings("ignore:Duplicate name")
def test_update_loaded_zipped_store(test_data_path, test_temp_path):
    base_zip_location = test_data_path / "store.zip"
    copied_zip_location = test_temp_path / "copy.zip"
    shutil.copy(base_zip_location, copied_zip_location)

    new_record = Record(
        id="added_record",
        content="This record is new"
    )
    first_store = ZippedChromaDBStore(path=copied_zip_location)
    first_store_original_records = first_store.get_all()
    first_store.add_record(new_record)
    first_store.update_zipfile()

    del first_store

    second_store = ZippedChromaDBStore(path=copied_zip_location)
    second_store_records = second_store.get_all()

    del second_store
    os.remove(copied_zip_location)

    assert len(second_store_records) - len(first_store_original_records) == 1
    assert new_record in second_store_records
