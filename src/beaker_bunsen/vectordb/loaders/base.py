import uuid
from abc import ABC, abstractmethod
from typing import Optional

from ..types import Resource, Default, DefaultType


class BaseLoader(ABC):

    SLUG: str
    URI_SCHEME: str

    locations: Optional[list[str]]
    metadata: Optional[dict]

    def __init__(
            self,
            locations: list[str] | None = None,
            metadata: dict | None = None
        ) -> None:
        super().__init__()
        self.locations = locations
        if metadata:
            self.metadata = metadata
        else:
            self.metadata = {}

    @abstractmethod
    def discover(
        self,
        locations: list[str] | DefaultType = Default,
        metadata: dict | DefaultType = Default,
    ):
        ...

    @abstractmethod
    def read(
        self,
        location: str,
        base: str = "",
    ):
        ...

    @classmethod
    def get_id_for_resource(cls, resource: Resource):
        # Is this check valid? Is it broken to have resource without a URI?
        # Do we need to be able to fetch it from the URI later on, even if it contains the full document content?
        if resource.uri:
            return f"{cls.SLUG}:{resource.uri}"
        else:
            return f"{cls.SLUG}:{uuid.uuid4()}"
