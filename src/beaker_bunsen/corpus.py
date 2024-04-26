from typing import Optional

from .vectordb.chromadb_store import ChromaDBLocalStore
from .vectordb.vector_store import VectorStore
from .vectordb.loaders import BaseLoader, BaseCodeLoader, LocalFileLoader, PythonLibraryLoader
from .vectordb.embedders import BaseEmbedder, DocumentationEmbedder
from .vectordb.types import LoadableResource, Embedding, Image, Metadata, QueryResponse, QueryResult, RecordBundle, EmbeddingFunction


class Corpus:
    """
    A corpus is a single, self-contained interface for querying over documents and other records embedded in a vector database.
    """

    store: VectorStore
    default_embedding_function: EmbeddingFunction|None

    def __init__(
            self,
            store: VectorStore,
            default_embedding_function: EmbeddingFunction|None
    ) -> None:
        self.store = store
        self.default_embedding_function = default_embedding_function

    @classmethod
    def from_zip(cls, zipfile_fullpath: str):
        pass

    @classmethod
    def from_dir(cls, fullpath: str):
        pass

    def add_records(
            self,
            embedder: BaseEmbedder,
            loader: BaseLoader|None = None,
        ):
        pass

    def save_to(self, output: str):
        pass

    def query(self):
        pass
