from typing import Iterator, Type

from beaker_bunsen.vectordb.loaders.base import BaseLoader
from beaker_bunsen.vectordb.types import EmbeddingFunction
from beaker_bunsen.vectordb.vector_store import VectorStore

from ..types import Resource, Record
from .base import BaseEmbedder
from ..loaders.schemes import read_from_uri
from ..util.helpers import count_words
from ..util.splitters import TextSplitter, RecursiveCharacterTextSplitter


class DocumentEmbedder(BaseEmbedder):

    splitter_class: Type[TextSplitter] = RecursiveCharacterTextSplitter

    def __init__(
        self,
        store: VectorStore,
        loader: BaseLoader | None = None,
        embedding_function: EmbeddingFunction | None = None,
        chunk_size: int = 2000,
        chunk_overlap: int = 100,
        splitter: TextSplitter =  None,
    ) -> None:
        self.splitter = splitter
        super().__init__(store, loader, embedding_function, chunk_size, chunk_overlap)

    def get_splitter(self, resource: Resource):
        if self.splitter:
            return self.splitter
        splitter = self.splitter_class(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        return splitter

    def prepare_records_from_resource(self, resource: Resource) -> Iterator[Record]:
        content = None
        if resource.content:
            content = resource.content
        elif resource.file_handle and not resource.file_handle.closed:
            try:
                resource.file_handle.seek(0)
            except IOError:
                pass
            content = resource.file_handle.read()
        elif resource.uri:
            content = read_from_uri(resource.uri)

        if content is None:
            raise ValueError(f"Can't retrieve content for resource {resource}")

        if isinstance(content, (str, bytes)) and len(content) == 0:
            # Empty file, no chunks to yield
            return

        splitter = self.get_splitter(resource)
        for i, content_chunk in enumerate(
                splitter.split_text(content),
                start=1
        ):
            record = Record(
                id=f"{resource.id}:{i}",
                uri=resource.uri,
                metadata=resource.metadata,
                content=content_chunk,
            )
            yield record
