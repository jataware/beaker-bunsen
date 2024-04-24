import pytest
from beaker_bunsen.vectordb.util.helpers import count_words, extract_md_codeblocks, extract_json


def test_word_count():
    count5 = "This sentence has five words."
    count7 = """
This
block
has
so many
different        words


"""
    assert count_words(count5) == 5
    assert count_words(count7) == 7
    with pytest.raises(ValueError):
        assert count_words(None) == 0
    with pytest.raises(ValueError):
        assert count_words(512) == 0


def test_extract_codeblocks():
    md_doc = '''
# this is some normal markdown.

Ooh so clean.

```python
print("""hello world""")
assert(True)
```

## Other code
```
{"I": "might be JSON, but I'm not Marked as such"}
```

## Last code:

```json
{
  "This": "is",
  "valid": "JSON",
  "yes": true
}
```
'''

    extractions = extract_md_codeblocks(md_doc)
    json_blocks = extract_json(md_doc)

    empty_block = extract_json("")

    print(f"{extractions=}")
    print(f"{json_blocks=}")

    assert len(extractions) == 3
    assert extractions[0][1] == "python"
    assert extractions[0][0].startswith('print("""hello')

    assert extractions[1][1] is None

    assert len(json_blocks) == 1
    assert isinstance(json_blocks[0], str)
    assert json_blocks[0].startswith("{")

    assert len(empty_block) == 0
