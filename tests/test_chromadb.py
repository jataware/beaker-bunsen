# Use pysqlite3-bin library instead of OS pysqlite3 which may be an incompatible version
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
from pathlib import Path
import pytest
from beaker_bunsen.vectordb.chromadb_store import ChromaDBLocalStore, Record

@pytest.fixture()
def chromadb_store(tmp_path_factory):
    store_path = str(tmp_path_factory.mktemp("test"))
    store = ChromaDBLocalStore(path=store_path, settings={'default_partition': "testing"})
    return store

@pytest.fixture()
def test_data_path():
    return Path(__file__).parent.absolute() / "data"

def test_add_record(chromadb_store):
    new_record = Record(
        id='test1',
        content="Hello world",
        metadata={'descr': 'first test', 'v': 1}
    )

    before_count = len(chromadb_store.get_all())
    chromadb_store.add_record(new_record)
    after_count = len(chromadb_store.get_all())

    record_from_db = chromadb_store.get_record("test1")
    assert after_count - before_count == 1
    assert isinstance(record_from_db, Record)
    assert record_from_db.id == 'test1'
    assert record_from_db.content == 'Hello world'
    assert record_from_db.metadata.get('descr') == 'first test'
    assert record_from_db.metadata.get('v') == 1
    assert record_from_db.embedding is None
    assert record_from_db.image is None
    assert record_from_db.uri is None


def test_add_bundle(chromadb_store):
    bundle = [
        Record(
            id='test2',
            content="What is past is prologue.",
            metadata={'source': 'The Tempest'}
        ),
        Record(
            id='test3',
            content="It is the east, and Juliet the sun.",
            # metadata={},
        ),
        Record(
            id='test4',
            content="I knew him, Horatio",
            metadata={'source': 'Hamlet'}
        ),
        Record(
            id='test5',
            content="Neither a borrower, nor a lender be.",
            # metadata={},
        ),
    ]


    before_count = len(chromadb_store.get_all())
    chromadb_store.add_records(bundle)
    after_count = len(chromadb_store.get_all())
    assert after_count - before_count == len(bundle)
    test2, test3, test4, test5 = chromadb_store.get_records(["test2", "test3", "test4", "test5"])

    assert after_count - before_count == len(bundle)
    assert test2.id and test2.content and test2.metadata and not (test2.image or test2.uri or test2.embedding)
    assert test3.id and test3.content and not (test3.image or test3.uri or test3.embedding or test3.metadata)
    assert test4.id and test4.content and test4.metadata and not (test4.image or test4.uri or test4.embedding)
    assert test5.id and test5.content and not (test5.image or test5.uri or test5.embedding or test5.metadata)
    assert test2.id == "test2" and test3.id == "test3" and test4.id == "test4" and test5.id == "test5"
    assert test3.content == "It is the east, and Juliet the sun."
    assert test2.metadata['source'] == "The Tempest"

def test_add_empty_bundle(chromadb_store):
    bundle = []

    before_count = len(chromadb_store.get_all())
    chromadb_store.add_records(bundle)
    after_count = len(chromadb_store.get_all())

    assert before_count == after_count == 0

def test_single_query(chromadb_store):
    "how to test query best?"
    bundle = [
        Record(
            id="spaghetti",
            content="""Spaghetti (Italian: [spagetti]) is a long, thin, solid, cylindrical pasta. It is a staple of traditional Italian cuisine.
            Like other pasta, spaghetti is made of milled wheat, water, and sometimes enriched with vitamins and minerals.
            Italian spaghetti is typically made from durum-wheat semolina."""
        ),
        Record(
            id="new_south_wales",
            content="""New South Wales (commonly abbreviated as NSW) is a state on the east coast of Australia.
            It borders Queensland to the north, Victoria to the south, and South Australia to the west.
            Its coast borders the Coral and Tasman Seas to the east."""
        ),
        Record(
            id="italy",
            content="""Italy, officially the Italian Republic, is a country in Southern and Western Europe.
            It is located on a peninsula that extends into the middle of the Mediterranean Sea, with the Alps on its northern land border, as well as several islands, notably Sicily and Sardinia.
            Italy shares its borders with France, Switzerland, Austria, Slovenia and two enclaves: Vatican City and San Marino.
            """
        ),
    ]

    chromadb_store.add_records(bundle)

    pasta_results = chromadb_store.query("pasta")
    food_results = chromadb_store.query("food")
    kangaroo_results = chromadb_store.query("kangaroo")
    land_results = chromadb_store.query("land")

    pasta_match_1, pasta_match_2 = pasta_results["matches"][:2]
    pasta_record_1, pasta_record_2 = pasta_match_1["record"], pasta_match_2["record"]

    top_food_match = food_results["matches"][0]
    top_kangaroo_match = kangaroo_results["matches"][0]

    top_2_land_matches = land_results["matches"][:2]
    top_2_land_ids = map(lambda match: match["record"].id, top_2_land_matches)

    assert pasta_record_1.id == "spaghetti"
    assert pasta_record_2.id == "italy"
    assert top_food_match["record"].id == "spaghetti"
    assert isinstance(top_food_match["distance"], float)
    assert top_kangaroo_match["record"].id == "new_south_wales"
    assert set(top_2_land_ids) == set(["italy", "new_south_wales"])

def test_multi_query(chromadb_store):
    "how to test query best?"
    bundle = [
        Record(
            id="spaghetti",
            content="""Spaghetti (Italian: [spagetti]) is a long, thin, solid, cylindrical pasta. It is a staple of traditional Italian cuisine.
            Like other pasta, spaghetti is made of milled wheat, water, and sometimes enriched with vitamins and minerals.
            Italian spaghetti is typically made from durum-wheat semolina."""
        ),
        Record(
            id="new_south_wales",
            content="""New South Wales (commonly abbreviated as NSW) is a state on the east coast of Australia.
            It borders Queensland to the north, Victoria to the south, and South Australia to the west.
            Its coast borders the Coral and Tasman Seas to the east."""
        ),
        Record(
            id="italy",
            content="""Italy, officially the Italian Republic, is a country in Southern and Western Europe.
            It is located on a peninsula that extends into the middle of the Mediterranean Sea, with the Alps on its northern land border, as well as several islands, notably Sicily and Sardinia.
            Italy shares its borders with France, Switzerland, Austria, Slovenia and two enclaves: Vatican City and San Marino.
            """
        ),
    ]

    chromadb_store.add_records(bundle)

    multi_results = chromadb_store.query_multi(["pasta", "food", "kangaroo", "land"])

    assert len(multi_results) == 4
    result1, result2, result3, result4 = multi_results

    assert result1["query"] == "pasta"
    assert result1["matches"][0]["record"].id == "spaghetti"
    assert result1["matches"][1]["record"].id == "italy"
    assert result2["query"] == "food"
    assert result2["matches"][0]["record"].id == "spaghetti"
    assert result3["query"] == "kangaroo"
    assert result3["matches"][0]["record"].id == "new_south_wales"
    assert set([result4["matches"][0]["record"].id, result4["matches"][1]["record"].id]) == set(["italy", "new_south_wales"])

def test_query_limit(chromadb_store):
    bundle = [
        Record(id=f"record{i}", content=f"document {i}")
        for i in range(50)
    ]

    chromadb_store.add_records(bundle)
    count = len(chromadb_store.get_all())

    assert count == 50

    results = chromadb_store.query("document", limit=12)
    mresults = chromadb_store.query_multi(["document", "record"], limit=18)

    assert len(results["matches"]) == 12

    assert len(mresults) == 2
    assert len(mresults[0]["matches"]) == 18
    assert len(mresults[1]["matches"]) == 18
