from typing import Iterator

from beaker_bunsen.vectordb.types import LoadableResource, Record

from .base import BaseEmbedder


class ExampleEmbedder(BaseEmbedder):

    def prepare_records_from_resource(self, resource: LoadableResource) -> Iterator[Record]:
        yield from super().prepare_records_from_resource(resource)
