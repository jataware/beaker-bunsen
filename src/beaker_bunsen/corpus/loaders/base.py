import uuid
from abc import ABC, abstractmethod
from typing import Optional

from ..types import Default, DefaultType
from ..resources import Resource, ResourceFilter


class BaseLoader(ABC):

    SLUG: str
    URI_SCHEME: str

    locations: Optional[list[str]]
    metadata: Optional[dict]
    filter: ResourceFilter

    def __init__(
            self,
            locations: list[str] | None = None,
            metadata: dict | None = None,
            exclusions: list[str] | None = None,
            filter: ResourceFilter | None = None,
        ) -> None:
        super().__init__()
        self.exclusions = exclusions or []
        self.metadata = metadata or {}
        self.filter = filter
        if locations:
            parsed_locations, parsed_exclusions = self.parse_locations(locations)
            self.locations = parsed_locations
            self.exclusions.extend(parsed_exclusions)
        else:
            self.locations = locations

    @abstractmethod
    def discover(
        self,
        locations: list[str] | DefaultType = Default,
        metadata: dict | DefaultType = Default,
        exclusions: list[str] | DefaultType = Default,
        filter: ResourceFilter | DefaultType = Default,
        *args,
        **kwargs,
    ):
        ...

    @abstractmethod
    def read(
        self,
        location: str,
        base: str = "",
    ):
        ...


    def parse_locations(
        self,
        locations: list[str],
    ) -> tuple[list[str], list[str]]:
        exclusions = []
        for location in locations[:]:
            if str(location).startswith("!"):
                locations.remove(location)
                exclusion_value = str(location).removeprefix('!')
                exclusions.append(exclusion_value)
        return locations, exclusions


    def should_exclude(
        self,
        location: str,
        exclusions: list[str] | DefaultType = Default
    ):
        if exclusions is Default:
            exclusions = self.exclusions
        for exclusion in exclusions:
            if exclusion in location:
                return True
        return False

    @classmethod
    def get_id_for_resource(cls, resource: Resource):
        # Is this check valid? Is it broken to have resource without a URI?
        # Do we need to be able to fetch it from the URI later on, even if it contains the full document content?
        if resource.uri:
            return f"{cls.SLUG}:{resource.uri}"
        else:
            return f"{cls.SLUG}:{uuid.uuid4()}"
