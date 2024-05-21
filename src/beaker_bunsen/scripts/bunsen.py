import click
import datetime
import json
import os
import os.path
import toml
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import openai

from ..vectordb.types import Resource
from ..vectordb.loaders.schemes import unmap_scheme, read_from_uri
from ..vectordb.loaders.code_library_loader import RCRANLocalCache


def find_pyproject_file() -> Path | None:
    cwd = Path.cwd()
    for path in [cwd, *cwd.parents]:
        potential_file = path / "pyproject.toml"
        if potential_file.is_file():
            return potential_file
    return None


@click.group()
def cli():
    """
    CLI Tooling to help build Bunsen contexts
    """
    pass


# TODO: Add optional param for setting destination
@cli.command()
@click.argument("locations", type=str, required=False, nargs=-1)
def extract_examples(locations: list[str]):

    dest = 'examples-unverified'
    if not os.path.exists(dest):
        os.makedirs(dest)

    sources: dict[str, list[str]] = defaultdict(lambda: [])
    if locations:
        bad_sources = []
        for location in locations:
            parsed_uri = urlparse(location)
            if not parsed_uri.scheme or parsed_uri.scheme == "file":
                source = Path(location)
                if not (source.is_dir() or source.is_file()):
                    bad_sources.append(source)
                else:
                    sources["file"].append(source.absolute())
        if bad_sources:
            raise click.UsageError(f"source(s) {', '.join(bad_sources)} are not valid.")
    else:
        # Get locations from config
        pyproject_file_path = find_pyproject_file()
        if pyproject_file_path:
            with pyproject_file_path.open() as pyproject_file:
                pyproject_config = toml.load(pyproject_file)
            bunsen_config = pyproject_config.get("tool", {}).get("hatch", {}).get("build", {}).get("hooks", {}).get("bunsen", {})
            sources["py-mod"].extend(
                bunsen_config.get("python_libraries", [])
            )
            sources["rcran-package"].extend(
                bunsen_config.get("r_cran_libraries", [])
            )
            documentation_path = bunsen_config.get("documentation_path", None)
            if documentation_path and Path(documentation_path).exists():
                sources["documentation"].append(
                    documentation_path
                )
            # TODO: We probably shouldn't extract example from the examples, so skipping, but keeping in case we change our mind soon.
            # examples_path = bunsen_config.get("examples_path", None)
            # if examples_path and Path(examples_path).exists():
            #     sources["examples"].append(
            #         examples_path
            #         # f"examples:{examples_path}"
            #     )

        if not pyproject_file_path or not bunsen_config:
            raise click.UsageError(f"No locations provided and unable to find a bunsen configuration in the directory tree.")


    with RCRANLocalCache(locations=sources["rcran-package"]):
        resource_list: list[Resource] = []
        for scheme, scheme_locations in sources.items():
            scheme_cls = unmap_scheme(scheme)

            loader_cls = scheme_cls.default_loader()
            loader = loader_cls()
            resource_list.extend(
                loader.discover(scheme_locations)
            )

        existing_example_nums = [filename.split('_')[1] for filename in os.listdir(dest)]
        num = 1
        try:
            if existing_example_nums:
                num = max(map(int, existing_example_nums)) + 1
        except:
            pass

        # TODO: Remove this
        print(os.listdir(dest))
        print(f"Num: {num}")
        print(existing_example_nums)

        for resource in resource_list:
            if resource.content:
                content = resource.content
            else:
                if resource.file_handle and not resource.file_handle.closed and resource.file_handle.readable():
                    content = resource.file_handle.read()
                else:
                    content = read_from_uri(resource.uri)

            prompt = """
A document is provided below. It contains line numbers on the left, the content on the right, with the sides separated by ` : `.
The provided document may be a source code file, a documentation page, an executable notebook, or hand extracted examples created by hand.
It may contain one or more curated examples as for how to accomplish something using relevant libraries.
Please identify any such examples and generate a short description of the purpose of the example code, along with the line number on which it occurs.
Also, make sure to include a prelude of code that contains any imports or definitions needed so the example is as complete as possible and has everything it needs to run as a stand-alone code block.
The prelude will later be combined with the example to help use the libraries these documents are related to.
Please ensure that all imports and definitions in the prelude are complete. Do not use statements like "put your code here..." or summarize what should be done.
Do not identify/extract regular source code from files as examples. Only extract unique tasks that demonstrate how to properly use the library.
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
                "".join(f"{line_no:6} : {line}" for line_no, line in enumerate(content.splitlines(keepends=True), start=1)),
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
                "resource_d": resource.id,
                "source_uri": resource.uri,
                "generated_at": datetime.datetime.utcnow().isoformat(),
                "source_sha256_hash": "TODO",
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
                continue

            click.echo(f"Found {len(example_list)} examples in {resource.uri}")
            for example_num, example in enumerate(example_list, start=1):
                example_filename = os.path.join(dest, f"example_{num}_{example_num}.md")
                example_metadata_filename = f"{example_filename}.metadata"
                start = int(example["start_line"]) - 1
                stop = int(example["stop_line"])
                example_code = "".join(content.splitlines(keepends=True)[start:stop])
                example_metadata = {
                    **metadata,
                    "start_line": start,
                    "stop_line": stop,
                }

                with open(example_filename, "w") as example_file, open(example_metadata_filename, "w") as example_metadata_file:
                    example_file.write(f"""
# Description
{example["description"]}

# Code
```
{example["prelude"]}
{example_code}
```
""".lstrip())
                    json.dump(example_metadata, example_metadata_file, indent=2)

            # Iterate source file num for next loop
            num += 1
