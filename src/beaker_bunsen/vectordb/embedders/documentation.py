from typing import Iterator

from ..types import Resource, Record
from .base import BaseEmbedder
from .document import DocumentEmbedder
from ..loaders.schemes import read_from_uri
from ..util.helpers import count_words
from ..util.splitters import RecursiveCharacterTextSplitter


class DocumentationEmbedder(DocumentEmbedder):
    pass
