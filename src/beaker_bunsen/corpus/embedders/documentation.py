from typing import Iterator

from ..resources import Resource
from .base import BaseEmbedder
from .document import DocumentEmbedder
from ..loaders.schemes import read_from_uri
from ..util.helpers import count_words
from ..util.splitters import RecursiveCharacterTextSplitter


class DocumentationEmbedder(DocumentEmbedder):
    def get_splitter(self, resource: Resource):
        if '.' in resource.uri:
            _, extension = resource.uri.rsplit('.', maxsplit=1)
            if extension in RecursiveCharacterTextSplitter.LANGUAGES_BY_EXTENSION:
                return RecursiveCharacterTextSplitter.from_extension(
                    extension=extension,
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap
                )
        # If no file extension, use the default
        # TODO: Try to determine file type in other ways?
        return self.splitter_class(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap
        )
