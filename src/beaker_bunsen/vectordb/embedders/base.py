from typing import Iterator

from .. import logger
from ..loaders.base import BaseLoader
from ..types import LoadableResource, Record, RecordBundle, EmbeddingFunction
from ..vector_store import VectorStore


class BaseEmbedder:
    loader: BaseLoader
    store: VectorStore
    embedding_function: EmbeddingFunction | None
    chunk_size: int
    chunk_overlap: int

    def __init__(
            self,
            loader: BaseLoader,
            store: VectorStore,
            embedding_function: EmbeddingFunction | None = None,
            chunk_size: int = 2000,
            chunk_overlap: int = 100,
        ) -> None:

        self.loader = loader
        self.store = store
        self.embedding_function = embedding_function
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def prepare_records_from_resource(self, resource: LoadableResource) -> Iterator[Record]:
        record = Record(
            id=resource.id,
            uri=resource.uri,
            metadata=resource.metadata,
        )
        if resource.content:
            record.content = resource.content
        elif resource.file_handle:
            try:
                resource.file_handle.seek(0)
            except IOError:
                pass
            record.content = resource.file_handle.read()
        yield record


    def ingest(
            self,
            locations: list[str] = None,
            partition: str = None,
            metadata: dict = None,
            embedding_function: EmbeddingFunction = None,
            batch_size: int = 15,
        ):

        batching_enabled = isinstance(batch_size, int) and batch_size >= 0
        batch = []
        for loadable in self.loader.discover(locations=locations, metadata=metadata):
            for record in self.prepare_records_from_resource(resource=loadable):

                if embedding_function:
                    record.embedding = embedding_function(loadable)
                elif self.embedding_function:
                    record.embedding = self.embedding_function(loadable)

                batch.append(record)

                # If batch size is not a positive number, never commit batches and just fall through to the final add
                # outside the loop.
                if batching_enabled and len(batch) >= batch_size:
                    logger.debug(f"Adding intermediate batch of {len(batch)} records")
                    self.store.add_records(bundle=batch, partition=partition)
                    batch = []
        # Final add for anything not added in a batch above
        if batch:
            logger.debug(f"Adding final batch of {len(batch)} records")
            self.store.add_records(bundle=batch, partition=partition)
