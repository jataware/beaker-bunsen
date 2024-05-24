import enum
import inspect
import sys
from io import FileIO
from functools import cache
from pathlib import Path
from typing import Any, Literal, TypeAlias

from ..types import (
    Default, DefaultType, RecordID, Image, Metadata, URI
)

class ResourceType(enum.Enum):
    Generic = "generic"
    Code = "code"
    Document = "document"
    Documentation = "documentation"
    Example = "example"


def _is_resource(obj: Any):
    return bool(
        inspect.isclass(obj)
        and issubclass(obj, Resource)
    )


@cache
def get_resource_cls(resource_type: ResourceType):
    current_module = sys.modules[__name__]
    for _cls_name, cls in inspect.getmembers(current_module, predicate=_is_resource):
        if getattr(cls, "resource_type", None) == resource_type:
            return cls



class Resource:
    """

    """
    resource_type: ResourceType = ResourceType.Generic

    uri: str|URI
    id: RecordID|None = None
    content: str|bytes|Image|None = None
    file_handle: FileIO|None = None
    metadata: Metadata | None = None
    basedir: str|Path = ""

    def __init__(self,
        uri: str,
        id: RecordID | None = None,
        content: str | bytes | Image | None = None,
        file_handle: FileIO | None = None,
        metadata: Metadata  |  None = None,
        basedir: str | Path = "",
    ) -> None:
        self.uri = URI(uri)
        self.id = id
        self.content = content
        self.file_handle = file_handle
        self.metadata = metadata
        self.basedir = basedir

        if self.content is None and self.file_handle is None:
            raise ValueError("Either content or file_handle must be provided.")

    def read(self):
        from ..loaders.schemes import read_from_uri
        if self.content:
            return self.content
        elif self.file_handle:
            try:
                self.file_handle.seek(0)
            except IOError:
                pass
            return self.file_handle.read()
        elif self.uri:
            return read_from_uri(self.uri)
        else:
            return None


class CodeResource(Resource):
    resource_type = ResourceType.Code


class DocumentResource(Resource):
    resource_type = ResourceType.Document


class DocumentationResource(Resource):
    resource_type = ResourceType.Documentation


class ExampleResource(Resource):
    resource_type = ResourceType.Example
