from typing import TYPE_CHECKING
from ..types import DefaultType, Default

from ..util.splitters import TextSplitter, RecursiveCharacterTextSplitter


if TYPE_CHECKING:
    from .resource import Resource


def find_splitter_for_resource(
    resource: "Resource",
    chunk_size: int | DefaultType = 2000,
    chunk_overlap: int | DefaultType = 100,
) -> TextSplitter | None:
    from .resource import CodeResource, DocumentationResource, DocumentResource, ExampleResource, ResourceType
    if chunk_size is Default:
        chunk_size = 2000
    if chunk_overlap is Default:
        chunk_overlap = 100

    # Images are never chunked. Returning None indicates to not split.
    if resource.resource_type == ResourceType.Image:
        return None

    # Examples are currently not chunked, but may be required in the future if examples grow very large.
    # In such a case, we will probably want to rethink how we use examples.
    if isinstance(resource, ExampleResource):
        return None

    # Check extension for pre-mapped recursive splitter
    if '.' in resource.uri:
        _, extension = resource.uri.rsplit('.', maxsplit=1)
        if extension in RecursiveCharacterTextSplitter.LANGUAGES_BY_EXTENSION:
            return RecursiveCharacterTextSplitter.from_extension(
                extension=extension,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

    # For code and documents of unprepared type, use default chunking
    if isinstance(resource, (CodeResource, DocumentResource, DocumentationResource)):
        return RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
        )

    # Finally, the default
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
