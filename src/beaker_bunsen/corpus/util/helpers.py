import os
from collections import deque
from pathlib import Path

import tiktoken


def count_words(source: str) -> int:
    """Count the number of words in a string. A word is denoted by whitespace."""
    if not isinstance(source, (str, bytes)):
        raise ValueError("Not a string")
    return len(source.split())


def count_tokens(
        source: str,
        model_or_encoding: str = None
    ):
    if not isinstance(source, (str, bytes)):
        raise ValueError("Not a string")

    encoding = None
    if model_or_encoding is None:
        encoding = tiktoken.get_encoding("cl100k_base")  # Default to encoding used by GPT-4
    else:
        # Check if we are provided an encoding name
        if model_or_encoding in tiktoken.list_encoding_names():
            encoding = tiktoken.get_encoding(model_or_encoding)
        # Check if provide a model name ()
        elif (
            model_or_encoding in tiktoken.model.MODEL_TO_ENCODING
            or any(model_or_encoding.startswith(prefix) for prefix in tiktoken.model.MODEL_PREFIX_TO_ENCODING.keys())
        ):
            encoding = tiktoken.encoding_for_model(model_or_encoding)

    if encoding is None:
        raise ValueError(f"Unable to match '{model_or_encoding}' to a model or encoding in the tiktoken library")

    return len(encoding.encode(source))


def extract_md_codeblocks(source: str) -> list[tuple[str, str|None]]:
    """
    Extracts markdown fenced code blocks, along with the code type, if provided.
    See https://www.markdownguide.org/extended-syntax/#fenced-code-blocks
    """
    result = []
    all_parts = deque(source.split('```'))
    while len(all_parts) > 1:
        _ = all_parts.popleft()
        codeblock = all_parts.popleft()
        codetype, code = codeblock.split("\n", maxsplit=1)
        if not codetype:
            codetype = None
        result.append((code, codetype))
    return result


def extract_json(source: str) -> list[str]:
    """
    Returns only the code for any json code blocks in the source.
    """
    return [codeblock for codeblock, codetype in extract_md_codeblocks(source) if codetype and codetype.lower() == "json"]


def common_path_portion(paths: list[str | Path]) -> str:
    """
    Takes a list of paths and returns the common portion that all the paths are contained within.
    """
    if not paths:
        return ""
    paths = [Path(path) for path in paths]
    path_parts = [path.parts for path in paths]
    max_steps = min(len(parts) for parts in path_parts)
    for step in range(max_steps):
        step_parts = [parts[step] for parts in path_parts]
        if not all(part == step_parts[0] for part in step_parts):
            break
    if step == 0:
        return ""
    else:
        return os.path.join(*path_parts[0][0:step])
