# Use pysqlite3-bin library instead of OS pysqlite3 which may be an incompatible version
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
import pytest
from pathlib import Path

from beaker_bunsen.vectordb.types import Resource
from beaker_bunsen.vectordb.chromadb_store import ChromaDBLocalStore
from beaker_bunsen.vectordb.embedders.base import BaseEmbedder
from beaker_bunsen.vectordb.loaders.local_file_loader import LocalFileLoader
from beaker_bunsen.vectordb.embedders.examples import ExampleEmbedder

@pytest.fixture()
def chromadb_store_path(tmp_path_factory):
    return str(tmp_path_factory.mktemp("test"))


@pytest.fixture()
def test_data_paths():
    data = Path(__file__).parent / "data"
    return [data / "examples"]


@pytest.fixture()
def chromadb_store(tmp_path_factory):
    store_path = str(tmp_path_factory.mktemp("test"))
    store = ChromaDBLocalStore(path=store_path, settings={'default_partition': "testing"})
    return store




def test_empty_example(chromadb_store):
    embedder = ExampleEmbedder(store=chromadb_store)
    test_resource = Resource(
        uri="test:test",
        content=""
    )

    with pytest.raises(ValueError):
        record = next(embedder.prepare_records_from_resource(test_resource), None)

def test_missing_description(chromadb_store):
    embedder = ExampleEmbedder(store=chromadb_store)
    test_resource = Resource(
        uri="test:test",
        content="""
# Code
```python
This is my code.
```
""".strip()
    )

    with pytest.raises(ValueError):
        record = next(embedder.prepare_records_from_resource(test_resource), None)

def test_bad_markdown(chromadb_store):
    from io import BytesIO
    embedder = ExampleEmbedder(store=chromadb_store)
    test_resource = Resource(
        uri="test:test",
        content=BytesIO(b"This cannot be parsed")
    )

    with pytest.raises(ValueError):
        record = next(embedder.prepare_records_from_resource(test_resource), None)

def test_no_headings(chromadb_store):
    embedder = ExampleEmbedder(store=chromadb_store)
    test_resource = Resource(
        uri="test:test",
        content="""
*This is valid markdown*

```javascript
this.is_valid()
```

But there are no headings
""".strip()
    )

    with pytest.raises(ValueError, ):
        record = next(embedder.prepare_records_from_resource(test_resource), None)


def test_valid_content(chromadb_store):
    embedder = ExampleEmbedder(store=chromadb_store)
    content = """
# Description
This is a test example

# Code
```python
This is some python code.
```

""".strip()
    test_resource = Resource(
        uri="test:test",
        content=content
    )

    record = next(embedder.prepare_records_from_resource(test_resource), None)

    assert record.content == content

def test_example_ingest(test_data_paths, chromadb_store):
    loader = LocalFileLoader(locations=test_data_paths)
    embedder = ExampleEmbedder(
        store=chromadb_store,
        loader=loader,
    )

    embedder.ingest(partition="examples")

    resources = list(loader.discover())
    records = chromadb_store.get_all(partition="examples")

    example_count = len(resources)
    record_count = len(records)

    assert example_count == record_count
    assert set([resource.uri for resource in resources]) == set([record.uri for record in records])
    assert all([len(record.content) > 1 for record in records])
