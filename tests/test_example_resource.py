import os
import pytest
from pathlib import Path

from beaker_bunsen.corpus.resources import Resource, ExampleResource
from beaker_bunsen.corpus.vector_stores.chromadb_store import ChromaDBLocalStore
from beaker_bunsen.corpus.loaders.local_file_loader import LocalFileLoader
from beaker_bunsen.corpus.embedders import Embedder
from beaker_bunsen.corpus.corpus import Corpus

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

    with pytest.raises(ValueError):
        test_resource = ExampleResource(
            uri="examples:test",
            content="",
            content_is_complete=True,
        )
        record = next(test_resource.as_records(), None)
    assert "record" not in locals()

def test_missing_description(chromadb_store):
    with pytest.raises(ValueError):
        test_resource = ExampleResource(
            uri="examples:test",
            content="""
# Code
```python
This is my code.
```
    """.strip(),
            content_is_complete=True,
        )

        record = next(test_resource.as_records(), None)
    assert "record" not in locals()

def test_bad_markdown(chromadb_store):
    from io import BytesIO
    with pytest.raises(ValueError):
        test_resource = ExampleResource(
            uri="examples:test",
            content=BytesIO(b"This cannot be parsed"),
            content_is_complete=True,
        )
        record = next(test_resource.as_records(), None)
    assert "record" not in locals()

def test_no_headings(chromadb_store):
    with pytest.raises(ValueError, ):
        test_resource = ExampleResource(
            uri="examples:test",
            content="""
*This is valid markdown*

```javascript
this.is_valid()
```

But there are no headings
""".strip(),
            content_is_complete=True,
        )

        record = next(test_resource.as_records(), None)
    assert "record" not in locals()


def test_valid_content(chromadb_store):
    content = """
# Description
This is a test example

# Code
```python
This is some python code.
```

""".strip()
    test_resource = ExampleResource(
        uri="examples:test",
        content=content,
        content_is_complete=True
    )

    record = next(test_resource.as_records(), None)

    assert record.content == content

def test_example_ingest(test_data_paths, chromadb_store):
    loader = LocalFileLoader(locations=test_data_paths)
    locations = [f"examples:{path}" for path in test_data_paths]

    corpus = Corpus(store=chromadb_store)
    corpus.ingest(locations)

    resources = list(loader.discover())
    records = chromadb_store.get_all(partition="examples")

    example_count = len(resources)
    record_count = len(records)

    assert example_count == record_count
    assert set([resource.uri for resource in resources]) == set([record.uri for record in records])
    assert all([len(record.content) > 1 for record in records])
