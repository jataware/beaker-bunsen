from typing import Iterator

from ..types import LoadableResource, Record
from .base import BaseEmbedder
from ..util.helpers import count_words
from ..util.splitters import RecursiveCharacterTextSplitter


class DocumentationEmbedder(BaseEmbedder):

    def prepare_records_from_resource(self, resource: LoadableResource) -> Iterator[Record]:
        content = None
        if resource.content:
            content = resource.content
        elif resource.file_handle and not resource.file_handle.closed:
            try:
                resource.file_handle.seek(0)
            except IOError:
                pass
            content = resource.file_handle.read()

        if not content:
            raise ValueError(f"Can't retrieve content for resource {resource}")

        splitter = RecursiveCharacterTextSplitter()
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
