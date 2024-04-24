import numpy as np
from dataclasses import dataclass, field
from io import FileIO
from numpy.typing import NDArray
from typing import Any, Union, Callable, Sequence, TypedDict, Optional


# Define types
RecordID = Union[str, int]

Document = str

NDImage = NDArray[Union[np.uint, np.int_, np.float_]]
RawImage = Union[Sequence[int], Sequence[float]]
Image = Union[bytearray, bytes, RawImage, NDImage]
Metadata = dict
Embedding = Union[Sequence[float], Sequence[int], np.ndarray]


@dataclass
class Record:
    id: RecordID
    embedding: Embedding|None = None
    document: Document|None = None
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
class LoadableResource:
    """

    """
    uri: str
    id: RecordID|None = field(default=None)
    content: str|bytes|Image|None = None
    file_handle: FileIO|None = None
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self):
        if self.content is None and self.file_handle is None:
            raise ValueError("Either content or file_handle must be provided.")
