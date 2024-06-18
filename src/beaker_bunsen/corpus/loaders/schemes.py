import importlib
import inspect
import os
import os.path
import sys
import zipfile
from abc import ABC, abstractmethod
from functools import cache
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..types import URI
if TYPE_CHECKING:
    from .. import Corpus
    from .base import BaseLoader


def _is_scheme(obj: Any):
    return bool(
        inspect.isclass(obj)
        and issubclass(obj, Scheme)
        and callable(getattr(obj, "read", None))
    )


@cache
def all_schemes():
    current_module = sys.modules[__name__]
    member_list: list[tuple[str, Scheme]] = inspect.getmembers(current_module, predicate=_is_scheme)
    classes: list[Scheme] = [cls for _, cls in member_list]
    return classes


@cache
def unmap_scheme(scheme: str):
    schemes = all_schemes()
    for cls in schemes:
        cls_uri_scheme = getattr(cls, "URI_SCHEME", None)
        if cls_uri_scheme is not None and cls_uri_scheme == scheme:
            return cls
    # Go through a second time, checking aliases. Keeping as two loops to always prefer primary schemes over overlap with aliases.
    for cls in schemes:
        if scheme in cls.ALIASES:
            return cls


def determine_scheme(uri: URI | str | Path) -> "Scheme | None":
    uri = URI(uri)
    scheme_cls = unmap_scheme(uri.scheme)
    if scheme_cls:
            return scheme_cls
    else:
        raise ValueError(f"Unable to identify scheme '{uri.scheme}' in uri '{uri}'")


def read_from_uri(
    uri: str,
    *args,
    **kwargs,
) -> bytes:
    scheme_cls = determine_scheme(uri)
    return scheme_cls.read(uri, *args, **kwargs)


class Scheme(ABC):
    URI_SCHEME: str
    ALIASES: list[str] = []

    @classmethod
    def default_loader(cls) -> "BaseLoader":
        from .local_file_loader import LocalFileLoader
        return LocalFileLoader()

    @classmethod
    @abstractmethod
    def read(
        cls,
        uri: str,
        *args,
        **kwargs,
    ) -> bytes | str:
        ...

    @classmethod
    @abstractmethod
    def join_parts(cls, *parts: list[str]) -> str:
        ...

    @classmethod
    def get_uri_for_location(
        cls,
        location: str,
        base: str = "",
    ):
        if not location:
            raise ValueError(f"Value '{location}' is not a valid location for a URI.")
        if base:
            return f"{cls.URI_SCHEME}:{cls.join_parts(base, location)}"
        else:
            return f"{cls.URI_SCHEME}:{location}"


class LocalFileScheme(Scheme):
    URI_SCHEME = 'file'

    @classmethod
    def default_loader(cls) -> "BaseLoader":
        from .local_file_loader import LocalFileLoader
        return LocalFileLoader()

    @classmethod
    def join_parts(cls, *parts: list[str]) -> str:
        return os.path.join(*parts)

    @classmethod
    def read(
        cls,
        uri: URI | str,
        base_dir: str | Path = "",
        *args,
        **kwargs,
    ) -> bytes | str:
        uri = URI(uri)
        if uri.scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme '{uri.scheme}' does not match expected scheme '{cls.URI_SCHEME}'.")
        if not uri.path.startswith('/'):
            path = os.path.join(base_dir, uri.path)
        else:
            path = uri.path
        try:
            with open(path, 'r') as resource_file:
                result = resource_file.read()
        except UnicodeDecodeError:
            with open(path, 'rb') as resource_file:
                result = resource_file.read()
        return result


class ExampleScheme(LocalFileScheme):
    URI_SCHEME = 'examples'

    @classmethod
    def default_loader(cls) -> "BaseLoader":
        from .local_file_loader import LocalFileLoader
        from ..resources import ResourceType
        return LocalFileLoader(resource_type=ResourceType.Example)


class DocumentationScheme(LocalFileScheme):
    URI_SCHEME = 'documentation'

    @classmethod
    def default_loader(cls) -> "BaseLoader":
        from .local_file_loader import LocalFileLoader
        from ..resources import ResourceType
        return LocalFileLoader(resource_type=ResourceType.Documentation)


class PythonModuleScheme(Scheme):
    URI_SCHEME = 'py-mod'
    ALIASES = [
        "python",
        "python3",
    ]

    @classmethod
    def default_loader(cls) -> "BaseLoader":
        from .code_library_loader import PythonLibraryLoader
        return PythonLibraryLoader()

    @staticmethod
    def get_module_path(mod_name) -> str | None:
        # Look for file by just looking for the file
        # First, use the loaders provided by the sys.meta_path
        head, *tail = mod_name.split('.')
        for loader in sys.meta_path:
            if not hasattr(loader, "find_spec"):
                continue
            spec = loader.find_spec(head, None)
            if not spec:
                continue

            file_paths = []
            if spec.origin is not None:
                file_paths.append(spec.origin)
            if isinstance(spec.submodule_search_locations, list):
                file_paths.extend(spec.submodule_search_locations)
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    if tail:
                        file_path = os.path.split(file_path)[0]
                for submod in tail:
                    file_path = os.path.join(file_path, submod)

                if os.path.isdir(file_path):
                    file_path = os.path.join(file_path, '__init__.py')
                if not os.path.isfile(file_path) and os.path.isfile(f"{file_path}.py"):
                    file_path = f"{file_path}.py"

                if os.path.isfile(file_path):
                    return file_path

        # Try to get the file via internal Python methodology, but executes the parent modules(s)
        spec = importlib.util.find_spec(mod_name)
        if spec is not None:
            if spec.loader and hasattr(spec.loader, 'get_filename'):
                return spec.loader.get_filename()
            elif spec.origin:
                return spec.origin


    @classmethod
    def join_parts(cls, *parts: list[str]) -> str:
        return ".".join(parts)

    @classmethod
    def read(
        cls,
        uri: str,
        *args,
        **kwargs,
    ) -> bytes | str:
        uri = URI(uri)
        if uri.scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme '{uri.scheme}' does not match expected scheme '{cls.URI_SCHEME}'.")

        mod_name = uri.path
        file_path = cls.get_module_path(mod_name)

        if file_path and os.path.isfile(file_path):
            with open(file_path, 'r') as resource_file:
                result = resource_file.read()
            return result

        raise FileNotFoundError(f"Unable to locate a file for module `{mod_name}`")


class S3Scheme(Scheme):
    URI_SCHEME = 's3'

    @classmethod
    def join_parts(cls, *parts: list[str]) -> str:
        return os.path.join(*parts)

    @classmethod
    def read(
        cls,
        uri: str,
        *args,
        **kwargs,
    ):
        # TODO: boto3?
        return ""


class ZipfileScheme(Scheme):
    URI_SCHEME = 'zipped-file'

    @classmethod
    def get_uri_for_location(
        cls,
        location: str,
        base: str = "",
    ):
        zipfile_path = Path(base)
        if not (
            zipfile_path.is_absolute() and zipfile_path.is_file() and str(zipfile_path).endswith(".zip")
        ):
            raise ValueError(f"Argument `base` must be an absolute path that points to a zipfile.")
        if not location:
            raise ValueError(f"Value '{location}' is not a valid location for a URI.")

        return f"{cls.URI_SCHEME}://{base}#{location}"

    @classmethod
    def join_parts(cls, *parts: list[str]) -> str:
        return os.path.join(*parts)

    @classmethod
    def read(
        cls,
        uri: str,
        *args,
        **kwargs,
    ):
        uri = URI(uri)
        if uri.scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme '{uri.scheme}' does not match expected scheme '{cls.URI_SCHEME}'.")
        zipfile_path = uri.path
        inner_file = uri.fragment
        with zipfile.ZipFile(zipfile_path) as zipfile_fh:
            with zipfile_fh.open(inner_file) as inner_file_fh:
                content = inner_file_fh.read()
        try:
            return content.decode()
        except UnicodeDecodeError:
            return content


class CorpusResourceScheme(Scheme):
    URI_SCHEME = 'corpus'

    @classmethod
    def get_uri_for_location(
        cls,
        location: str,
        base: str = "",
    ):
        if not location:
            raise ValueError(f"Value '{location}' is not a valid location for a resource in a corpus.")

        return f"{cls.URI_SCHEME}:{location}"

    @classmethod
    def read(
        cls,
        uri: str,
        corpus: "Corpus",
        *args,
        **kwargs,
    ):
        uri = URI(uri)
        if uri.scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme '{uri.scheme}' does not match expected scheme '{cls.URI_SCHEME}'.")
        return corpus.read_resource(uri.path)


class RCranScheme(Scheme):
    URI_SCHEME = "rcran-package"
    ALIASES = [
        "r_cran",
        "rlang",
        "r",
        "irkernel",
    ]

    local_file_cache: dict[str, str] = {}

    @classmethod
    def default_loader(cls) -> "BaseLoader":
        from .code_library_loader import RCRANSourceLoader
        return RCRANSourceLoader()

    @classmethod
    def get_uri_for_location(
        cls,
        location: str,
        base: str = "",
    ):
        if not (location and base):
            raise ValueError(f"Value '{location}' in base '{base}' is not a valid rcran-package location.")

        return f"{cls.URI_SCHEME}:{location}#{base}"

    @classmethod
    def read(
        cls,
        uri: str,
        *args,
        **kwargs,
    ):
        from .code_library_loader import RCRANLocalCache
        uri = URI(uri)
        if uri.scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme '{uri.scheme}' does not match expected scheme '{cls.URI_SCHEME}'.")

        package = uri.fragment
        subpath = uri.path
        with RCRANLocalCache([package]) as cache:
            target_file = Path(cache[package]) / subpath
            with target_file.open() as source:
                content = source.read()
        return content
