import numpy as np
from dataclasses import dataclass
from numpy.typing import NDArray
from typing import Any, Union, Sequence, TypedDict, TYPE_CHECKING, TypeAlias
from typing_extensions import Self
from urllib.parse import urlparse, ParseResult


# Define types
class DefaultType:
    """Default sentinel class"""
    def __bool__(self):
        return False

    def __repr__(self) -> str:
        return 'Default'

# Default sentinel for indicating that default arguments should be used
Default: DefaultType = DefaultType()

RecordID: TypeAlias = Union[str, int]

RecordContent: TypeAlias = str

NDImage: TypeAlias = NDArray[Union[np.uint, np.int_, np.float_]]
RawImage: TypeAlias = Union[Sequence[int], Sequence[float]]
Image: TypeAlias = Union[bytearray, bytes, RawImage, NDImage]
Metadata: TypeAlias = dict
Embedding: TypeAlias = Union[Sequence[float], Sequence[int], np.ndarray]


class URI(str):
    _parts: ParseResult
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str

    def __new__(cls, object: Any) -> Self:
        if isinstance(object, cls):
            return object
        if object is None:
            return None
        self = str.__new__(cls, object, )
        self._parts = urlparse(self)
        return self

    def __getattr__(self, name) -> Any:
        if name in ParseResult._fields:
            return getattr(self._parts, name)
        raise AttributeError(f"Attribute {name} does not exist on object {repr(self)}.")

@dataclass
class Record:
    id: RecordID
    embedding: Embedding|None = None
    content: RecordContent|None = None
    image: Image|None = None
    uri: str|URI|None = None
    metadata: Metadata|None = None

    def __post_init__(self, *args, **kwargs):
        self.uri = URI(self.uri)

RecordBundle = Sequence[Record]


class QueryResult(TypedDict):
    record: Record
    distance: float


class QueryResponse(TypedDict):
    query: str
    matches: list[QueryResult]


class ValidationError(ValueError):
    pass
