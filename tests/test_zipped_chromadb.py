# Use pysqlite3-bin library instead of OS pysqlite3 which may be an incompatible version
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import pytest
import shutil
from pathlib import Path
from zipfile import ZipFile

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
    second_store_new_record = next((record for record in second_store_records if record.id == new_record.id ), None)

    del second_store
    os.remove(copied_zip_location)

    assert len(second_store_records) - len(first_store_original_records) == 1
    assert len(second_store_records) > 1 and len(first_store_original_records) > 0
    assert new_record in second_store_records
    assert second_store_new_record == new_record  # Records are equal
    assert second_store_new_record is not new_record  # But records are not the exact same item


def test_clone_unsaved_store(test_data_path, test_temp_path):
    zip_location = test_temp_path / "store.zip"

    orig_store = ZippedChromaDBStore(path=zip_location)
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

    orig_store.add_records(bundle)
    orig_records = orig_store.get_all()
    orig_identifier = getattr(orig_store.client, '_identifier', None)
    orig_zip_exists = zip_location.exists()

    cloned_store = orig_store.clone()
    cloned_records = cloned_store.get_all()
    cloned_identifier = getattr(cloned_store.client, '_identifier', None)
    cloned_zip_exists = zip_location.exists()


    assert cloned_store is not orig_store
    assert len(orig_records) > 1
    assert len(cloned_records) > 1
    assert len(orig_records) == len(cloned_records)
    assert set(r.id for r in orig_records) == set(r.id for r in cloned_records)
    assert cloned_store.zipfile == orig_store.zipfile
    assert orig_identifier and cloned_identifier
    assert orig_identifier != cloned_identifier
    assert orig_zip_exists == False
    assert cloned_zip_exists == False

def test_clone_saved_store(test_data_path, test_temp_path):
    source_location = test_data_path / "store.zip"

    orig_store = ZippedChromaDBStore(path=source_location)
    orig_records = orig_store.get_all()
    orig_identifier = getattr(orig_store.client, '_identifier', None)
    orig_zip_exists = source_location.exists()

    cloned_zip_location = test_temp_path / "store.zip"
    cloned_store = orig_store.clone(path=cloned_zip_location)

    cloned_store.add_record(Record(
        id="added_to_clone", content="Baa, Baaa"
    ))

    cloned_records = cloned_store.get_all()
    cloned_identifier = getattr(cloned_store.client, '_identifier', None)
    cloned_zip_exists_preupdate = cloned_zip_location.exists()
    cloned_store.update_zipfile()
    cloned_zip_exists_postupdate = cloned_zip_location.exists()

    assert cloned_store is not orig_store
    assert len(orig_records) > 1
    assert len(cloned_records) > 1
    assert len(cloned_records) == len(orig_records) + 1
    assert set(r.id for r in cloned_records) - set(r.id for r in orig_records) == set(['added_to_clone'])
    assert cloned_store.zipfile != orig_store.zipfile
    assert orig_identifier and cloned_identifier
    assert orig_identifier != cloned_identifier
    assert orig_zip_exists == True
    assert cloned_zip_exists_preupdate == False
    assert cloned_zip_exists_postupdate == True


def test_clone_zipfiles_correct(test_data_path, test_temp_path):
    source_location = test_data_path / "store.zip"
    orig_store = ZippedChromaDBStore(path=source_location)

    cloned_zip_location = test_temp_path / "store.zip"
    cloned_store = orig_store.clone(path=cloned_zip_location)
    cloned_store.add_record(Record(
        id="added_to_clone", content="Baa, Baaa"
    ))
    cloned_store.update_zipfile()
    del cloned_store
    verif_store = ZippedChromaDBStore(path=cloned_zip_location)

    orig_records = orig_store.get_all()
    verif_records = verif_store.get_all()

    with ZipFile(source_location, "r") as orig_zipfile:
        orig_filelist = orig_zipfile.filelist
    with ZipFile(cloned_zip_location, "r") as cloned_zipfile:
        cloned_filelist = cloned_zipfile.filelist

    assert len(verif_records) == len(orig_records) + 1
    assert set(r.id for r in verif_records) - set(r.id for r in orig_records) == set(['added_to_clone'])
    assert source_location.stat().st_mtime != cloned_zip_location.stat().st_mtime
    assert [f.filename for f in orig_filelist] == [f.filename for f in cloned_filelist]
