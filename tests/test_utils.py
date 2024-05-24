import pytest
from beaker_bunsen.corpus.util.helpers import count_words, extract_md_codeblocks, extract_json, common_path_portion


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


def test_distinct_path_portion():
    paths_usr_lib = [
        "/usr/lib/apt/apt-helper",
        "/usr/lib/apt/apt.systemd.daily",
        "/usr/lib/apt/methods/store",
        "/usr/lib/apt/methods/file",
        "/usr/lib/apt/methods/ftp",
        "/usr/lib/apt/methods/http",
        "/usr/lib/ssl/misc/tsget.pl",
        "/usr/lib/ssl/misc/CA.pl",
        "/usr/lib/systemd/system/apt-daily-upgrade.timer",
        "/usr/lib/systemd/system/apt-daily.service",
        "/usr/lib/systemd/system/fstrim.service",
        "/usr/lib/systemd/system/e2scrub_all.service",
        "/usr/lib/systemd/system/e2scrub_all.timer",
        "/usr/lib/udev/rules.d/85-hwclock.rules",
        "/usr/lib/udev/rules.d/96-e2scrub.rules",
        "/usr/lib/udev/hwclock-set",
    ]
    paths_usr_lib_apt = [
        "/usr/lib/apt/apt-helper",
        "/usr/lib/apt/apt.systemd.daily",
        "/usr/lib/apt/methods/store",
        "/usr/lib/apt/methods/file",
        "/usr/lib/apt/methods/ftp",
    ]
    paths_usr_lib_systemd = [
        "/usr/lib/systemd/system/apt-daily-upgrade.timer",
        "/usr/lib/systemd/system/apt-daily.service",
        "/usr/lib/systemd/system/fstrim.service",
        "/usr/lib/systemd/system/e2scrub_all.service",
        "/usr/lib/systemd/system/e2scrub_all.timer",
    ]
    paths_root = [
        "/home/user/bin/sort",
        "/etc/hosts",
        "/usr/lib/systemd/system/e2scrub_all.service",
        "/usr/lib/systemd/system/e2scrub_all.timer",
        "/usr/lib/udev/rules.d/85-hwclock.rules",
    ]
    paths_relative = [
        "/home/user/bin/sort",
        "lib/python/python3/dist-packages/numpy/random",
    ]
    paths_single = [
        "/usr/lib/systemd/system/e2scrub_all.service",
    ]

    assert common_path_portion(paths_usr_lib) == "/usr/lib"
    assert common_path_portion(paths_usr_lib_apt) == "/usr/lib/apt"
    assert common_path_portion(paths_usr_lib_systemd) == "/usr/lib/systemd/system"
    assert common_path_portion(paths_root) == "/"
    assert common_path_portion(paths_relative) == ""
    assert common_path_portion(paths_single) == "/usr/lib/systemd/system"
    assert common_path_portion([]) == ""
