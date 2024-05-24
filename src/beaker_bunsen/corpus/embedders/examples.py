import marko
from marko.md_renderer import MarkdownRenderer
from typing import Iterator

import marko.md_renderer

from ..types import Record
from ..resources import Resource

from .base import BaseEmbedder


class ExampleEmbedder(BaseEmbedder):

    def prepare_records_from_resource(self, resource: Resource) -> Iterator[Record]:
        content = resource.read()
        try:
            tree = marko.Parser().parse(content)
        except Exception as err:
            raise ValueError(
                f"Example file at `{resource.uri}` does not seem to be valid Example markdown file."
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
        for key in list(sections.keys()):
            if not sections[key]:
                del sections[key]

        # TODO: figure out if we're doing this here.
        # if "Code" in sections:
        #     code_node: marko.block.FencedCode | None = next(
        #         (node for node in sections["Code"] if node.get_type(snake_case=True) == "fenced_code"),
        #         None
        #     )
        #     code_lang = code_node.lang
        #     code_content = MarkdownRenderer().render_children(code_node).strip()
        #     # TODO: test code for ability to run

        if not sections:
            # TODO: Include link to docs once those exist.
            raise ValueError(f"Example file at `{resource.uri}` is empty or does not meet the expected format.")
        if "Description" not in sections:
            raise ValueError(f"Example file at `{resource.uri}` is missing the required 'Description' section.")

        record = Record(
            id=resource.id,
            uri=resource.uri,
            metadata=resource.metadata,
            content=content,
        )

        yield record
