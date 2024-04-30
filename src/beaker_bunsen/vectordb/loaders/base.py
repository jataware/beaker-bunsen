import uuid
from abc import ABC, abstractmethod
from typing import Optional

from ..types import Resource


class BaseLoader(ABC):

    SLUG: str
    URI_SCHEME: str

    locations: Optional[list[str]]
    metadata: Optional[dict]

    def __init__(
            self,
            locations: Optional[list[str]] = None,
            metadata: Optional[dict] = None
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
        locations: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ):
        ...

    @abstractmethod
    def load(self, uri: str):
        ...

    @classmethod
    def get_uri_for_location(cls, location: str):
        if not location:
            raise ValueError(f"Value '{location}' is not a valid location for a URI.")
        return f"{cls.URI_SCHEME}:{location}"


    @classmethod
    def get_id_for_resource(cls, resource: Resource):
        # Is this check valid? Is it broken to have resource without a URI?
        # Do we need to be able to fetch it from the URI later on, even if it contains the full document content?
        if resource.uri:
            return f"{cls.SLUG}:{resource.uri}"
        else:
            return f"{cls.SLUG}:{uuid.uuid4()}"
