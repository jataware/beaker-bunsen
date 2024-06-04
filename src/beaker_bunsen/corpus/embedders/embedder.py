
from ..protocols import EmbeddingFunction
from ..types import DefaultType, Default, ValidationError
from ..resources import Resource, find_splitter_for_resource
from ..util.logging import logger


class Embedder:
    embedding_function: EmbeddingFunction | None
    chunk_size: int = 2000
    chunk_overlap: int = 100

    def __init__(
            self,
            embedding_function: EmbeddingFunction | None = None,
            chunk_size: int | DefaultType = Default,
            chunk_overlap: int | DefaultType = Default,
        ) -> None:

        self.embedding_function = embedding_function
        self.chunk_size = chunk_size if chunk_size is not Default else self.__class__.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not Default else self.__class__.chunk_overlap

    def embed(
        self,
        resource: Resource,
        embedding_function: EmbeddingFunction = None,
        chunk_size: int | DefaultType = Default,
        chunk_overlap: int | DefaultType = Default,
    ):
        if embedding_function is None:
            embedding_function = self.embedding_function
        if chunk_size is Default:
            chunk_size = self.chunk_size
        if chunk_overlap is Default:
            chunk_overlap = self.chunk_overlap
        splitter = find_splitter_for_resource(resource, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        try:
            records = resource.as_records(splitter=splitter)
            # If there is a custom embedding function, apply that for each record
            if embedding_function:
                for record in records:
                    record.embedding = embedding_function(resource)
                    yield record
            else:
                yield from records
        except ValidationError:
            # Skip records that do not validate
            # TODO: Flags or similar for advanced control of validation error behavior? Default for now is to skip.
            pass
