import click
import datetime
import glob
import json
import os
import os.path
import re
import toml
from collections import defaultdict
from functools import reduce
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import openai

from ..corpus.types import Default, DefaultType, URI
from ..corpus.resources import Resource
from ..corpus.loaders.schemes import unmap_scheme, read_from_uri
from ..corpus.loaders.code_library_loader import RCRANLocalCache
from ..corpus.loaders.local_file_loader import LocalFileLoader

from .helpers import find_pyproject_file, calculate_content_hash


def generate_existing_example_map(
    example_dirs: list[str],
    base_map: DefaultType | dict[str, Any] = Default,  # TODO: Fix type
):
    if base_map is Default:
        map =  {
            "examples": {},
            "sources": {},
        }
    else:
        map = base_map

    resources = LocalFileLoader(locations=example_dirs).discover()
    for resource in resources:
        source_uri = resource.metadata.get("source_uri", None)
        if not source_uri:
            # If no source_uri, it's not an example that can checked for change.
            continue
        source_hash = resource.metadata.get("source_sha256_hash", None)
        # if source_uri in map and source_hash != map[source_uri]:
        #     raise KeyError("")
        example_path = resource.uri.path
        if source_uri in map["sources"]:
            # if source_hash != map["source"][source_uri]:
            #     raise KeyError("")
            map["sources"][source_uri]["example_files"].append(example_path)
        else:
            map["sources"][source_uri] = {
                "hash": source_hash,
                "example_files": [example_path,]
            }
        map["examples"][example_path] = {
            "hash": source_hash,
            "source": source_uri,
        }

    return map


# TODO: Add optional param for setting destination
@click.command()
@click.option("--force", is_flag=True, type=bool, default=False, required=False, help="Force processing files even if they haven't changed")
@click.option("--keep", is_flag=True, type=bool, default=False, required=False, help="Do not remove out-of-date examples when changes are detected")
@click.argument("locations", type=str, required=False, nargs=-1)
def extract_examples(locations: list[str], force: bool, keep: bool):
    """
    Extract examples from Bunsen config or specified locations for use in RAG
    """
    total_example_count = 0

    dest = 'examples-unverified'
    if not os.path.exists(dest):
        os.makedirs(dest)

    selected_locations = []
    if locations:
        bad_sources = []
        for location in locations:
            uri = URI(location)
            if not uri.scheme or uri.scheme == "file":
                source = Path(location)
                if not (source.is_dir() or source.is_file()):
                    bad_sources.append(source)
                else:
                    # sources["file"].append(f"file://{source.absolute()}")
                    selected_locations.append(f"file://{source.absolute()}")
        if bad_sources:
            raise click.UsageError(f"source(s) {', '.join(map(str, bad_sources))} are not valid.")
    else:
        # Get locations from config
        pyproject_file_path = find_pyproject_file()
        if pyproject_file_path:
            from beaker_bunsen.builder.bunsen_context import BunsenContextConfig
            bunsen_config = BunsenContextConfig.from_pyproject_toml(pyproject_file_path)
            selected_locations = bunsen_config.locations

        if not pyproject_file_path or not bunsen_config:
            raise click.UsageError(f"No locations provided and unable to find a bunsen configuration in the directory tree.")

    locations = selected_locations
    with RCRANLocalCache(locations=locations):
        resource_list: list[Resource] = []
        example_locations = [dest]
        click.echo("Collecting resources to inspect for examples:")
        for location in locations:
            uri_parts = urlparse(location)
            scheme = uri_parts.scheme
            # Don't extract examples from already identified/formatted examples
            if scheme == "examples":
                # Store example locations so we can track if found examples already exist
                example_locations.append(uri_parts.path)
                continue

            click.echo(f"  Inspecting location '{location}'")
            scheme_cls = unmap_scheme(scheme)

            loader = scheme_cls.default_loader()
            found_resources = list(loader.discover([location]))
            for resource in found_resources:
                click.echo(f"    Found resource '{resource.uri}'")
            resource_list.extend(
                found_resources
            )

        example_map = generate_existing_example_map([dest])

        click.echo(f"Found {len(resource_list)} resources to check for examples.\n")

        existing_example_nums = [filename.split('_')[1] for filename in os.listdir(dest)]
        num = 1
        try:
            if existing_example_nums:
                num = max(map(int, existing_example_nums)) + 1
        except:
            pass
        files_to_delete = []

        click.echo(f"Extracting examples from collected resources:")
        for resource in resource_list:
            if resource.content:
                content = resource.content
            else:
                if resource.file_handle and not resource.file_handle.closed and resource.file_handle.readable():
                    content = resource.file_handle.read()
                else:
                    content = read_from_uri(resource.uri)

            content_hash = calculate_content_hash(content)
            click.echo(f"  {resource.resource_type.name} resource {resource.uri}:")

            if resource.uri in example_map["sources"]:
                if example_map["sources"][resource.uri]["hash"] == content_hash:
                    if not force:
                        click.echo(f"    Hash for resource {resource.uri} has not changed for resource {resource.uri}. Still {content_hash}.\n    Use --force to force extraction.")
                        continue
                    else:
                        print(f"    Reprocessing resource {resource.uri} despite lack of change as --force is active.")
                # Since we are continuing to process the file, we must delete any original examples based on this file.
                files_to_delete.extend(example_map["sources"][resource.uri]["example_files"])

            content_lines = content.splitlines(keepends=True)
            prompt = """
A document is provided below. It contains line numbers on the left, the content on the right, with the sides separated by ` : `.
The provided document may be a source code file, a documentation page, an executable notebook, or hand extracted examples created by hand.
It may contain one or more curated examples as for how to accomplish something using relevant libraries.
Please identify any such examples and generate a short description of the purpose of the example code, along with the start/stop line numbers (inclusive) where the example occurs.
For example, if the example is a single line on the line labeled 34, both `start_line` and `stop_line` would be equal to 34.
If the example was spread of 5 lines, starting at line 12, the values would be `start_line` = 12, `stop_line` = 16.
Also, make sure to include a prelude of code that contains any imports or definitions needed so the example is as complete as possible and has everything it needs to run as a stand-alone code block.
The prelude will later be combined with the example to help use the libraries these documents are related to.
Please ensure that all imports and definitions in the prelude are complete. Do not use statements like "put your code here..." or summarize what should be done.
Do not identify/extract regular source code from files as examples. Only extract unique tasks that demonstrate how to properly use the library.
That is, all exracted examples should show usage of functions, not just the code that defines a function. Assume the user will be able to look up argument and parameter information.
You should err on the side of fewer, more complete examples which show an entire "step" of work rather than examples of subtasks.
As an example, if you find sample code where a dataset is sorted and a comparison function is defined to help sort, only extract one example that includes all the code. Do not create a separate example of how to define a comparison function.
If you do not find any examples in the document, do not generate one yourself. Instead return an empty list.

Please be sure to format your answer in json format as response object that matches this format with one object per example object in the `examples` list:
  {
    "examples": [
      {
        "description": str,
        "prelude": str,
        "start_line": int,
        "stop_line": int,
      },
      ...
    ]
  }

The document from which to extract begins below this line and runs until the end of the input:\n"""

            full_prompt = "\n".join([
                prompt,
                "".join(f"{line_no:6} : {line}" for line_no, line in enumerate(content_lines, start=1)),
            ])
            model = "gpt-4o"

            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": """
    You are a helpful assistant who is excellent at understanding and describing code and who always responds using JSON.
    You are helping to identify and explain code examples to allow for better understanding and use on how to use novel and
    interesting software libaries. These examples will help users to code in and/or use the covered software.
                        """.strip(),
                    },
                    {
                        "role": "user",
                        "content": full_prompt,
                    }
                ],
                response_format={"type": "json_object"},
            )

            metadata = {
                **resource.metadata,
                "resource_id": resource.id,
                "source_uri": resource.uri,
                "generated_at": datetime.datetime.utcnow().isoformat(),
                "source_sha256_hash": content_hash,
            }

            if not response:
                continue
            response_content = response.choices[0].message.content.strip()
            if not response_content:
                continue
            try:
                example_list = json.loads(response_content)["examples"]
            except json.JSONDecodeError as err:
                click.echo(f"Encountered error {err} when processing {resource.uri}")
                failure_file_path = os.path.join(dest, f"failure_{num}.txt")
                with open(failure_file_path, "w") as failure_file:
                    failure_file.write(
                        f"{response_content}\n"
                        f"{'====' * 20}\n"
                    )
                    json.dump(metadata, failure_file, indent=2)
                    failure_file.write(
                        f"\n{'====' * 20}\n"
                        f"{err}\n{err.msg}\n"
                    )
                continue

            if not example_list:
                click.echo("    No examples found.")
                continue
            click.echo(f"    {len(example_list)} examples extracted.")

            total_example_count += len(example_list)

            for example_num, example in enumerate(example_list, start=1):
                example_filename = os.path.join(dest, f"example_{num}_{example_num}.md")
                example_metadata_filename = f"{example_filename}.metadata"
                start = int(example["start_line"]) - 1
                stop = int(example["stop_line"])
                prelude_lines = example.get("prelude", "").splitlines(keepends=True)
                prelude = clean_codeblock(prelude_lines) if prelude_lines else ""
                example_code_lines = content_lines[start:stop]
                example_code = clean_codeblock(example_code_lines)

                example_metadata = {
                    **metadata,
                    "start_line": start,
                    "stop_line": stop,
                }

                example_file_contents = f"""
# Description
{example["description"]}

# Code
```
{prelude}
{example_code}
```
""".lstrip()


                with open(example_filename, "w") as example_file, open(example_metadata_filename, "w") as example_metadata_file:
                    example_file.write(example_file_contents)
                    json.dump(example_metadata, example_metadata_file, indent=2, default=(lambda o: str(o)))

            # Iterate source file num for next loop
            num += 1

        if files_to_delete and not keep:
            click.echo("Removing out-of-date examples due to updates in the resources. (Run with --keep flag to preserve out-of-date examples)")
            for file_to_delete in files_to_delete:
                os.remove(file_to_delete)
                click.echo(f"  {file_to_delete}")
    click.echo(f"\nA total of {total_example_count} examples extracted from {len(resource_list)} resources")


def should_ignore_line(line: str) -> bool:
    """
    Returns a boolean as to whether a particular line should be kept or ignored when importing code.
    We should ignore extraneous whitespace, code-block indicators, decorative lines, etc that do are not semantically
    meaningful.
    """
    # Todo: Other leading/trailing lines we need to clean?
    if (
        re.search(r'\S', line) == None  # Line does not contain at least one non-whitespace character
        or line.startswith('```')
    ):
        return True
    return False


def clean_codeblock(code: list[str]) -> str:
    if not code:
        return ""
    top, bottom = 0, len(code) - 1
    while should_ignore_line(code[top]) and top < len(code) - 1:
        top += 1
    while should_ignore_line(code[bottom]) and bottom > top:
        bottom -= 1
    split_lines = [re.split(r'([ \t])', line) for line in code[top:bottom]]
    line_count = len(split_lines)
    vertical_parts = list(zip(*split_lines))
    for idx, section in enumerate(vertical_parts):
        correct_size = len(section) == line_count
        all_match, _ = reduce(
            lambda match_tuple, next_val: (match_tuple[1] == next_val, match_tuple[1]),
            section,
            (True, section[0])
        )
        if not (correct_size and all_match):
            break
    else:
        idx = None
    unprefixed_lines = ["".join(split_line[idx:]) for split_line in split_lines]
    return "".join(unprefixed_lines)
