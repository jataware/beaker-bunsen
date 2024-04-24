# -*- coding: utf-8 -*-
import os
import re
from collections import deque


def count_words(source: str) -> int:
    """Count the number of words in a string. A word is denoted by whitespace."""
    if not isinstance(source, (str, bytes)):
        raise ValueError("Not a string")
    return len(source.split())



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
