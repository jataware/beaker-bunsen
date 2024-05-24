from typing import Iterator

from beaker_bunsen.corpus.loaders.base import BaseLoader
from beaker_bunsen.corpus.vector_stores.base_vector_store import VectorStore

from .document import DocumentEmbedder
from ..resources import Resource
from ..loaders.schemes import read_from_uri
from ..util.helpers import count_words
from ..util.splitters import RecursiveCharacterTextSplitter


class CodeEmbedder(DocumentEmbedder):

    SCHEME_MAP = {
        "py-mod": 'python',
    }

    def get_splitter(self, resource: Resource):
        scheme = resource.uri.scheme
        path = resource.uri.path
        language = self.SCHEME_MAP.get(scheme, None)
        if language and language in RecursiveCharacterTextSplitter.SEPARATORS_BY_LANGUAGE:
            return RecursiveCharacterTextSplitter.from_language(
                language=language,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
        if '.' in path:
            _, extension = path.rsplit('.', maxsplit=1)
            if extension in RecursiveCharacterTextSplitter.LANGUAGES_BY_EXTENSION:
                return RecursiveCharacterTextSplitter.from_extension(
                    extension=extension,
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap
                )
        return self.splitter_class(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )


class PythonEmbedder(CodeEmbedder):
    # TODO: Do we need this, or is CodeEmbedder enough?
    pass
