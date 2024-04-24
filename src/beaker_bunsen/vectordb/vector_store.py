from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Union, Sequence, TypedDict
from typing_extensions import Self
from numpy.typing import NDArray
import logging
import numpy as np

from .types import Record, RecordBundle, QueryResponse, Resource, EmbeddingFunction
from .loaders.base import BaseLoader


logger = logging.getLogger("beaker_bunsen")


class VectorStore(ABC):

    default_partition: str
    default_embedding_function: EmbeddingFunction|None
    store_settings: Any

    def __init__(
            self,
            settings: Any = None,
            default_partition: str|None = "default",
            default_embedding_function: EmbeddingFunction|None = None,
        ) -> None:
        if default_partition is not None:
            self.default_partition = default_partition
        else:
            self.default_partition = "default"
        self.default_embedding_function = default_embedding_function
        self.store_settings = settings

    @abstractmethod
    def get_partitions(self) -> list[str]:
        ...

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
        ids: Any,
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
    def update_record(
        self,
        record: Record,
        partition: str|None = None
    ):
        ...

    @abstractmethod
    def update_records(
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
        **kwargs,
        # TODO: Add extra filtering, as over metadata/subpartition/attribute/etc
    ) -> QueryResponse:
        ...

    @abstractmethod
    def query_multi(
        self,
        query_strings: list[str],
        partition: str | None = None,
        limit: int = -1,
        **kwargs,
    ) -> Sequence[QueryResponse]:
        ...

    @abstractmethod
    def clone(self, **kwargs) -> Self:
        ...

    @abstractmethod
    def save_to(
        self,
        destination: str,
        *args,
        **kwargs,
    ) -> str:
        ...
