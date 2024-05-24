import importlib
import inspect
from typing import Protocol, runtime_checkable
from typing_extensions import Self

from .resources import Resource
from .types import URI


@runtime_checkable
class EmbeddingFunction(Protocol):
    URI_SCHEME = "embedding"
    __name__: str

    def __call__(self, resource: Resource, *args, **kwargs) -> list[float]:
        ...

    @classmethod
    def get_uri(cls, value: Self | None) -> str | None:
        if value is None:
            return None
        func_name = value.__name__
        module = inspect.getmodule(value)
        spec = module.__spec__
        return f"{cls.URI_SCHEME}://{spec.name}#{func_name}"

    @classmethod
    def from_uri(cls, uri: URI | str | None) -> Self | None:
        if uri is None:
            return None
        uri = URI(uri)
        if uri.scheme != cls.URI_SCHEME:
            raise ValueError(f"Provided scheme ({uri.scheme}) does not match expected ({cls.URI_SCHEME})")
        mod_name = uri.netloc
        func_name = uri.fragment
        module = importlib.import_module(mod_name)
        func = getattr(module, func_name, None)
        if not isinstance(func, cls):
            raise ValueError(f"Function referenced by URI `{uri}` is does not satisfy the EmbeddingFunction protocol.")
