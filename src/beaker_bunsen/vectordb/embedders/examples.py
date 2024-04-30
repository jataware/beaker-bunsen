from typing import Iterator

from beaker_bunsen.vectordb.types import Resource, Record

from .base import BaseEmbedder


class ExampleEmbedder(BaseEmbedder):

    def prepare_records_from_resource(self, resource: Resource) -> Iterator[Record]:
        yield from super().prepare_records_from_resource(resource)
