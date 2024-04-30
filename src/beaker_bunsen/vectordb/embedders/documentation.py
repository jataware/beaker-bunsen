from typing import Iterator

from ..types import Resource, Record
from .base import BaseEmbedder
from ..loaders.schemes import read_from_uri
from ..util.helpers import count_words
from ..util.splitters import RecursiveCharacterTextSplitter


class DocumentationEmbedder(BaseEmbedder):

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


        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
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
