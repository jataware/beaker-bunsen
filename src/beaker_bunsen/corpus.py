import shutil
from collections import defaultdict
from pathlib import Path
from typing import Type

from .vectordb.chromadb_store import ChromaDBLocalStore, ZippedChromaDBStore
from .vectordb.vector_store import VectorStore
from .vectordb.loaders import BaseLoader, BaseCodeLoader, LocalFileLoader, PythonLibraryLoader
from .vectordb.embedders import BaseEmbedder, DocumentationEmbedder
from .vectordb.types import Record, Resource, Embedding, Image, Metadata, QueryResponse, QueryResult, RecordBundle, EmbeddingFunction


Default = Type[type(Ellipsis)]


class Corpus:
    """
    A corpus is a single, self-contained interface for querying over documents and other records embedded in a vector database.
    """
    embedder_map: dict[str, BaseEmbedder]

    store: VectorStore
    default_embedding_function: EmbeddingFunction | None

    def __init__(
            self,
            store: VectorStore,
            default_embedding_function: EmbeddingFunction | None = None,
    ) -> None:
        self.store = store
        self.default_embedding_function = default_embedding_function

    @classmethod
    def from_zip(cls, zipfile_fullpath: str):
        pass

    @classmethod
    def from_dir(cls, fullpath: str):
        pass

    def ingest(
            self,
            embedder_cls: Type[BaseEmbedder],
            loader: BaseLoader | Default = ...,
            base_metadata: dict | Default = ...,
            partition: str | Default = ...,
            embedding_function: EmbeddingFunction | Default = ...,
            batch_size: int | Default = ...,
    ):
        if loader is Ellipsis:
            loader = None

        if base_metadata is Ellipsis:
            base_metadata = {}
        optional_kwargs = {}
        if partition is not Ellipsis:
            optional_kwargs["partition"] = partition

        if embedding_function is Ellipsis:
            embedding_function = self.default_embedding_function
        if embedding_function not in (Ellipsis, None):
            optional_kwargs["embedding_function"] = embedding_function

        if batch_size is not Ellipsis:
            optional_kwargs["batch_size"] = batch_size

        embedder = embedder_cls(store=self.store)
        embedder.ingest(loader=loader, metadata=base_metadata, **optional_kwargs)

    def save_to_dir(self, save_dir: str|Path, overwrite: bool = False):
        if not isinstance(save_dir, Path):
            save_dir = Path(save_dir)
        if save_dir.exists():
            if not save_dir.is_dir():
                raise FileExistsError("Save destination `{save_dir}` already exists and is not a directory")
            has_contents = bool(next(save_dir.iterdir(), False))
            if has_contents:
                if not overwrite:
                    raise FileExistsError("Save destination `{save_dir}` is not empty and overwrite is set to False")
                else:
                    shutil.rmtree(save_dir)
                    save_dir.mkdir()

        zipfile = save_dir / "store.zip"
        resource_dir = save_dir / "resources"
        resource_dir.mkdir()

        temp_store = self.store.clone()

        partitions = self.store.get_partitions()
        # resources: dict[str, list[str]] = defaultdict(list)
        default_partition = self.store.default_partition
        default_store_embedding_function = self.store.default_embedding_function

        resources: dict[str, set[str]] = {
            partition: set() for partition in partitions
        }
        for partition in partitions:
            for record in temp_store.get_all(partition=partition):
                if record.uri:
                    resources[partition].add(record.uri)
        print(resources)






    def save_to_zip(self, output: str):
        pass

    def query(self):
        pass
