import json
import os
from collections import deque
from pathlib import Path
from typing import Optional

from .base import BaseLoader
from .schemes import LocalFileScheme, read_from_uri
from ..types import Resource, Default, DefaultType


class LocalFileLoader(BaseLoader):

    Scheme = LocalFileScheme
    SLUG = "local"

    def __init__(
        self,
        locations: list[str] | None = None,
        metadata: dict | None = None
    ):
        if locations:
            self._check_locations_exist(locations)
        super().__init__(locations, metadata)

    @staticmethod
    def _check_locations_exist(locations: list[str]):
        missing_locations = []
        for location in locations:
            if isinstance(location, Path):
                location = str(location.absolute())
            if not os.path.exists(location):
                missing_locations.append(location)
        if missing_locations:
            raise ValueError(f"Paths do not exist: {', '.join(missing_locations)}")

    @staticmethod
    def collapse_metadata(metadata_list: list[dict|None]):
        collapsed_metadata = {}
        for metadata in metadata_list:
            if metadata is not None:
                collapsed_metadata.update(metadata)
        return collapsed_metadata

    def discover(
        self,
        locations: list[str] | DefaultType = Default,
        metadata: dict | DefaultType = Default,
    ):
        # Validate locations if they are passed in. If they are not, use location from initialization.
        if locations is not Default:
            self._check_locations_exist(locations)
        else:
            locations = self.locations

        if locations is None:
            raise ValueError("No locations specified to discover local files")

        if metadata is Default:
            metadata = {}
            metadata.update(self.metadata)

        locations_queue = deque((location, [metadata]) for location in locations)
        while locations_queue:
            location, location_metadata = locations_queue.popleft()
            if isinstance(location, Path):
                location = str(location.absolute())
            if os.path.isdir(location):
                # Check for directory metadata file
                dir_metadata_path = os.path.join(location, '.metadata')
                if os.path.isfile(dir_metadata_path):
                    with open(dir_metadata_path, 'r') as metadata_file:
                        dir_metadata = json.load(metadata_file)
                        location_metadata.append(dir_metadata)
                locations_queue.extend((os.path.join(location, child), location_metadata[:]) for child in os.listdir(location) if not child.startswith('.'))
            # Skip pipes, symbolic links, and other non-file types
            # TODO: maybe allow by configuration
            elif os.path.isfile(location):
                if location.endswith(".metadata"):
                    # Don't load .metadata files as regular files.
                    # They should be found via the mechanisms below where they are looked for explicitly.
                    continue
                metadata_filename = f"{location}.metadata"
                if os.path.isfile(metadata_filename):
                    with open(metadata_filename, 'r') as metadata_file:
                        dir_metadata = json.load(metadata_file)
                        location_metadata.append(dir_metadata)

                metadata = self.collapse_metadata(location_metadata)
                with open(location, 'r') as doc:
                    resource = Resource(uri=self.Scheme.get_uri_for_location(location), file_handle=doc, metadata=metadata)
                    resource.id = self.get_id_for_resource(resource)
                    yield resource

    def read(self, location: str, base: str = ""):
        if location.startswith(self.Scheme.URI_SCHEME):
            uri = location
        else:
            uri = self.Scheme.get_uri_for_location(location, base=base)
        return read_from_uri(uri)
