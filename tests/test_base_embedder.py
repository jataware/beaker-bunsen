import os
import pytest
from pathlib import Path

from beaker_bunsen.corpus.resources import Resource
from beaker_bunsen.corpus.vector_stores.chromadb_store import ChromaDBLocalStore
from beaker_bunsen.corpus.embedders.embedder import Embedder
from beaker_bunsen.corpus.loaders.local_file_loader import LocalFileLoader

# @pytest.fixture()
# def chromadb_store_path(tmp_path_factory):
#     return str(tmp_path_factory.mktemp("test"))


# @pytest.fixture()
# def test_data_paths():
#     data = Path(__file__).parent / "data"
#     return [data / "documents", data / "examples"]


# def test_base_embedder(chromadb_store_path, test_data_paths):
#     store = ChromaDBLocalStore(path=chromadb_store_path)
#     loader = LocalFileLoader(locations=test_data_paths)
#     embedder = Embedder(
#         loader=loader,
#         store=store,
#     )

#     records_before_ingestion = store.get_all()
#     embedder.ingest()
#     ingested_records = store.get_all()

#     assert len(records_before_ingestion) == 0
#     assert len(ingested_records) > 0


# def test_embedder_ingest_with_metadata(chromadb_store_path, test_data_paths):
#     store = ChromaDBLocalStore(path=chromadb_store_path)
#     loader = LocalFileLoader(locations=test_data_paths)
#     embedder = Embedder(
#         loader=loader,
#         store=store,
#     )

#     embedder.ingest(metadata={"embedder": "test_metadata"})

#     ingested_records = store.get_all()
#     metadata_map = {os.path.basename(record.uri): record.metadata for record in ingested_records}

#     assert all('embedder' in record.metadata.keys() for record in ingested_records)
#     assert metadata_map["Lunar_Sample_Laboratory_Facility.html"] == {"embedder": "test_metadata"}
#     assert metadata_map["yorkshire.txt"] == {"embedder": "test_metadata", "source": "wikipedia", "url": "https://en.wikipedia.org/wiki/Yorkshire"}


# def test_embedder_ingest_location_override(chromadb_store_path, test_data_paths):
#     store = ChromaDBLocalStore(path=chromadb_store_path)
#     loader = LocalFileLoader(locations=[test_data_paths[0]])
#     embedder = Embedder(
#         loader=loader,
#         store=store,
#     )

#     embedder.ingest(locations=[test_data_paths[1]])
#     ingested_records = store.get_all()

#     default_loader_uris = [record.uri for record in loader.discover()]
#     ingested_uris = [record.uri for record in ingested_records]

#     assert len(ingested_records) > 0
#     assert ingested_uris != default_loader_uris


# def test_embedder_ingest_partition_override(chromadb_store_path, test_data_paths):
#     store = ChromaDBLocalStore(path=chromadb_store_path)
#     loader = LocalFileLoader(locations=test_data_paths)
#     embedder = Embedder(
#         loader=loader,
#         store=store,
#     )

#     embedder.ingest(partition="other")

#     records_in_default_partition = store.get_all()
#     records_in_other_partition = store.get_all(partition="other")

#     assert len(records_in_default_partition) == 0
#     assert len(records_in_other_partition) > 0


# def generate_embedding_function(start=0):
#     glob = {"count": start}
#     def embedding_function(resource: Resource, outer_ref=glob):
#         return_val = [float(outer_ref["count"])] * 384
#         outer_ref["count"] += 1
#         return return_val
#     return embedding_function


# def test_embedder_embedding_function(chromadb_store_path, test_data_paths):
#     store = ChromaDBLocalStore(path=chromadb_store_path)
#     loader = LocalFileLoader(locations=test_data_paths)
#     embedder = Embedder(
#         loader=loader,
#         store=store,
#         embedding_function=generate_embedding_function(1)
#     )

#     embedder.ingest()

#     ingested_records = store.get_all(include_embeddings=True)
#     first_five_embedding_values = sorted([record.embedding[0] for record in ingested_records])[:5]

#     assert first_five_embedding_values == [1.0, 2.0, 3.0, 4.0, 5.0]


# def test_embedder_embedding_function_override(chromadb_store_path, test_data_paths):
#     store = ChromaDBLocalStore(path=chromadb_store_path)
#     loader = LocalFileLoader(locations=test_data_paths)
#     embedder = Embedder(
#         loader=loader,
#         store=store,
#     )

#     embedder.ingest(
#         embedding_function=generate_embedding_function(10)
#     )

#     ingested_records = store.get_all(include_embeddings=True)
#     first_five_embedding_values = sorted([record.embedding[0] for record in ingested_records])[:5]

#     assert first_five_embedding_values == [10.0, 11.0, 12.0, 13.0, 14.0]
