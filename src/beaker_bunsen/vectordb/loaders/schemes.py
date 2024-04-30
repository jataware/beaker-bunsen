import os.path
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse


__all__ = [
    "LocalFileScheme",
]


def read_from_uri(
    uri: str,
    base_dir: str | Path = "",
) -> bytes:
    scheme = urlparse(uri).scheme
    for cls_name in __all__:
        cls = globals()[cls_name]
        cls_uri_scheme = getattr(cls, "URI_SCHEME", None)
        if cls_uri_scheme is not None and cls_uri_scheme == scheme and hasattr(cls, 'load'):
            return cls.load(uri, base_dir)
    else:
        raise ValueError(f"Unable to determine loader for scheme '{scheme}'")


class Scheme(ABC):
    URI_SCHEME: str

    @classmethod
    @abstractmethod
    def load(
        cls,
        uri: str,
        base_dir: str | Path = "",
    ):
        ...


class LocalFileScheme:
    URI_SCHEME = 'file'

    @classmethod
    def load(
        cls,
        uri: str,
        base_dir: str | Path = "",
    ) -> bytes:
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme '{parsed_uri.scheme}' does not match expected scheme '{cls.URI_SCHEME}'.")
        if not parsed_uri.path.startswith('/'):
            path = os.path.join(base_dir, parsed_uri.path)
        else:
            path = parsed_uri.path
        with open(path, 'rb') as resource_file:
            result = resource_file.read()
        return result
