from beaker_bunsen.vectordb.types import LoadableResource, Record
from .base import BaseEmbedder


class DocumentEmbedder(BaseEmbedder):

    def prepare_records_from_resource(self, loadable_resource: LoadableResource) -> Record:
        return super().prepare_records_from_resource(loadable_resource)
