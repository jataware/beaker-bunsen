from typing import Iterator

from beaker_bunsen.vectordb.loaders.base import BaseLoader
from beaker_bunsen.vectordb.types import EmbeddingFunction
from beaker_bunsen.vectordb.vector_store import VectorStore

from ..types import Resource, Record
from .base import BaseEmbedder
from .document import DocumentEmbedder
from ..loaders.schemes import read_from_uri
from ..util.helpers import count_words
from ..util.splitters import RecursiveCharacterTextSplitter


class CodeEmbedder(DocumentEmbedder):
    pass


class PythonEmbedder(CodeEmbedder):
    def get_splitter(self):
        splitter = RecursiveCharacterTextSplitter.from_language(
            language='.py',
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        return splitter
