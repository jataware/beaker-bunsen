from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Union, Callable, Sequence, TypedDict
from numpy.typing import NDArray
import logging
import numpy as np

from .types import Record, RecordBundle, QueryResponse, LoadableResource
from .loaders.base import BaseLoader


logger = logging.getLogger("beaker_bunsen")


class VectorStore(ABC):

    default_partition: str
    default_embedding_function: Callable|None

    def __init__(
            self,
            default_partition: str|None = "default",
            default_embedding_function: Callable|None = None
        ) -> None:
        if default_partition is not None:
            self.default_partition = default_partition
        else:
            self.default_partition = "default"
        self.default_embedding_function = default_embedding_function

    @abstractmethod
    def get_record(
        self,
        id: Any,
        partition: str|None = None,
    ) -> Record:
        ...

    @abstractmethod
    def get_records(
        self,
        ids: any,
        partition: str|None = None,
    ) -> Sequence[Record]:
        ...

    @abstractmethod
    def get_all(
        self,
        partition: str|None = None,
    ) -> Sequence[Record]:
        ...

    @abstractmethod
    def add_record(
        self,
        record: Record,
        partition: str|None = None
    ):
        ...

    @abstractmethod
    def add_records(
        self,
        bundle: RecordBundle,
        partition: str|None = None
    ):
        ...

    @abstractmethod
    def query(
        self,
        query_string: str,
        partition: str | None = None,
        limit: int = -1,
    ) -> QueryResponse:
        ...

    @abstractmethod
    def query_multi(
        self,
        query_strings: list[str],
        partition: str | None = None,
        limit: int = -1,
    ) -> Sequence[QueryResponse]:
        ...
