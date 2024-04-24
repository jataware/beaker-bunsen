import importlib
import inspect
import numpy as np
from dataclasses import dataclass, field
from io import FileIO
from numpy.typing import NDArray
from pathlib import Path
from typing import Any, Union, Sequence, TypedDict, Protocol, runtime_checkable
from typing_extensions import Self
from urllib.parse import urlparse


# Define types
class DefaultType:
    """Default sentinel class"""
    def __bool__(self):
        return False

# Default sentinel for indicating that default arguments should be used
Default = DefaultType()

RecordID = Union[str, int]

RecordContent = str

NDImage = NDArray[Union[np.uint, np.int_, np.float_]]
RawImage = Union[Sequence[int], Sequence[float]]
Image = Union[bytearray, bytes, RawImage, NDImage]
Metadata = dict
Embedding = Union[Sequence[float], Sequence[int], np.ndarray]


@dataclass
class Record:
    id: RecordID
    embedding: Embedding|None = None
    content: RecordContent|None = None
    image: Image|None = None
    uri: str|None = None
    metadata: Metadata|None = None


RecordBundle = Sequence[Record]

class QueryResult(TypedDict):
    record: Record
    distance: float


class QueryResponse(TypedDict):
    query: str
    matches: list[QueryResult]


@dataclass
class Resource:
    """

    """
    uri: str
    id: RecordID|None = field(default=None)
    content: str|bytes|Image|None = None
    file_handle: FileIO|None = None
    metadata: Metadata = field(default_factory=dict)
    basedir: str|Path = field(default="")

    def __post_init__(self):
        if self.content is None and self.file_handle is None:
            raise ValueError("Either content or file_handle must be provided.")

    # @property
    # def uri

    def read(self):
        pass


@runtime_checkable
class EmbeddingFunction(Protocol):
    URI_SCHEME = "embedding"
    __name__: str

    def __call__(self, resource: Resource, *args, **kwargs) -> list[float]:
        ...

    @classmethod
    def get_uri(cls, value: Self | None) -> str | None:
        if value is None:
            return None
        func_name = value.__name__
        module = inspect.getmodule(value)
        spec = module.__spec__
        return f"{cls.URI_SCHEME}://{spec.name}#{func_name}"

    @classmethod
    def from_uri(cls, uri: str | None) -> Self | None:
        if uri is None:
            return None
        uri_parts = urlparse(uri)
        scheme, mod_name, func_name = uri_parts.scheme, uri_parts.netloc, uri_parts.fragment
        if scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme ({scheme}) does not match expected ({cls.URI_SCHEME})")
        module = importlib.import_module(mod_name)
        func = getattr(module, func_name, None)
        if not isinstance(func, cls):
            raise ValueError(f"Function referenced by URI `{uri}` is does not satisfy the EmbeddingFunction protocol.")
