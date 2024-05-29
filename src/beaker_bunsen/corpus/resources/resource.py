import enum
import inspect
import marko
import sys
from io import FileIO
from functools import cache
from marko.md_renderer import MarkdownRenderer
from pathlib import Path
from typing import Any, Generator, TypeAlias, Optional, Callable

from ..types import (
    RecordID, Image, Metadata, URI, Record, ValidationError
)


class ResourceType(enum.Enum):
    Generic = "generic"
    Code = "code"
    Document = "document"
    Documentation = "documentation"
    Example = "example"
    Image = "image"


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


ResourceContentType: TypeAlias = str | bytes | Image

class Resource:
    """

    """
    resource_type: ResourceType = ResourceType.Generic
    default_partition: str = "default"

    uri: URI
    id: RecordID | None = None
    content: ResourceContentType | None = None
    file_handle: FileIO | None = None
    metadata: Metadata |  None = None
    basedir: str | Path = ""
    content_is_complete: bool | None = None
    validated: bool

    def __init__(self,
        uri: URI | str,
        id: RecordID | None = None,
        content: str | bytes | Image | None = None,
        file_handle: FileIO | None = None,
        metadata: Metadata  |  None = None,
        basedir: str | Path = "",
        content_is_complete: bool | None = None,
    ) -> None:
        self.uri = URI(uri)
        self.id = id
        self.content = content
        self.file_handle = file_handle
        self.metadata = metadata
        self.basedir = basedir
        self.content_is_complete = content_is_complete
        self.validated = False

        if self.content is None and self.file_handle is None:
            raise ValueError("Either content or file_handle must be provided when defining a resource.")

    def validate(self, content: ResourceContentType | None) -> None:
        """
        Should raise a ValueError if resource is not valid
        """
        pass

    def read(self):
        from ..loaders.schemes import read_from_uri
        if self.content_is_complete and self.content is not None:
            return self.content
        elif self.file_handle and not self.file_handle.closed:
            try:
                self.file_handle.seek(0)
            except IOError:
                pass
            return self.file_handle.read()
        elif self.uri:
            return read_from_uri(self.uri)
        else:
            return None

    def as_records(self, splitter=None) -> Generator[Record, None, None]:
        content = self.read()

        if content is None:
            raise ValueError(f"Unable to determine content for resource `{self.id}` @ `{self.uri}`")

        # Validate before use if needed
        if not self.validated:
            self.validate(content=content)

        if splitter is None:
            chunks = [content]
        else:
            chunks = splitter.split_text(content)

        for chunk_num, chunk in enumerate(
                chunks,
                start=1,
        ):
            record = Record(
                id=f"{self.id}:{chunk_num}",
                uri=self.uri,
                metadata=self.metadata,
                content=chunk,
            )
            yield record


class DocumentResource(Resource):
    resource_type = ResourceType.Document
    default_partition: str = "default"


class DocumentationResource(DocumentResource):
    resource_type = ResourceType.Documentation
    default_partition: str = "documentation"


class CodeResource(DocumentResource):
    resource_type = ResourceType.Code
    default_partition: str = "code"


class ExampleResource(Resource):
    resource_type = ResourceType.Example
    default_partition: str = "examples"

    def validate(self, content: ResourceContentType | None = None):
        if content is None:
            content = self.read()
        try:
            tree = marko.Parser().parse(content)
        except Exception as err:
            raise ValueError(
                f"Example file at `{self.uri}` does not seem to be valid Example markdown file."
            ) from err

        sections = {}

        current_section = None
        chunk = []
        for node in tree.children:
            if node.get_type(snake_case=True) == "heading":
                if current_section:
                    sections[current_section] = chunk
                    chunk = []
                current_section = MarkdownRenderer().render_children(node).strip()
            elif node.get_type(snake_case=True) == "blank_line":
                continue
            elif current_section:
                chunk.append(node)
        if current_section:
            sections[current_section] = chunk

        # Remove any empty sections that may have been defined but have no content
        for key in sections.keys():
            if len(sections[key]) == 0:
                del sections[key]

        if not sections:
            # TODO: Include link to docs once those exist.
            raise ValidationError(f"Example file at `{self.uri}` is empty or does not meet the expected format.")
        if "Description" not in sections:
            raise ValidationError(f"Example file at `{self.uri}` is missing the required 'Description' section.")
        self.validated = True


ResourceFilter: TypeAlias = Optional[Callable[[Resource], bool]]


def isCodeResource(resource: Resource) -> bool:
    return isinstance(resource, CodeResource)


def isDocumentResource(resource: Resource) -> bool:
    return isinstance(resource, DocumentResource)


def isDocumentationResource(resource: Resource) -> bool:
    return isinstance(resource, DocumentationResource)


def isExampleResource(resource: Resource) -> bool:
    return isinstance(resource, ExampleResource)


def isImageResource(resource: Resource) -> bool:
    return isinstance(resource, Resource) and resource.resource_type == ResourceType.Image
