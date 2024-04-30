import importlib
import importlib.util
import logging
import pkgutil
from collections import deque
from typing import Optional

from .base import BaseLoader
from ..types import Resource

logger = logging.getLogger("beaker_bunsen")

class BaseCodeLoader(BaseLoader):

    URI_SCHEME = "file"


class PythonLibraryLoader(BaseCodeLoader):

    SLUG = "python"

    def discover(
        self,
        locations: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ):
        """
        The `locations` should be Python packages, modules or submodules that are installed via the pyproject
        requirements.  Each location must be importable using the syntax `import {location}`, so you can include
        either top-level modules such as 'pandas' or submodules such as `pandas.plotting`.  The loader will recurse
        through and to include anything defined "below" the specified location in the import tree. I.e. location
        `pandas` will load all submodules, but `pandas.api.extensions` will not import any other submodules under
        `pandas.api.*` besides what is specified.

        Note: "from" import syntax is not valid. Loading a module loads the entire module and it's submodules and
        it is not possible to select only certain items from the module.

        Example: locations=["requests", "os.path", "pandas.core", "pandas.util"]
        """
        if locations is None:
            locations = self.locations
        if metadata is None:
            metadata = self.metadata

        modules_to_collect = deque()
        for module_name in locations:
            module_spec = importlib.util.find_spec(module_name)
            if module_spec is None:
                raise ValueError(f"Module '{module_name}' is not able to be imported. Please ensure that it is listed as a requirement and that 'require-runtime-dependencies' is enabled if error encountered during build.")
            modules_to_collect.append(module_spec)

        while modules_to_collect:
            module_spec = modules_to_collect.popleft()

            # TODO: Switch this to type of loader? SourceFileLoader works, ExtensionFileLoader doesn't...
            if not module_spec.origin.endswith('.py'):
                logger.info(f"Skipping importing non-python file {module_spec.origin}")
                continue

            # if module_spec.submodule_search_locations:
            if getattr(module_spec, "submodule_search_locations", []):
                subpkg_info: pkgutil.ModuleInfo = pkgutil.iter_modules(path=module_spec.submodule_search_locations)
                subpkg_specs = (info.module_finder.find_spec(info.name) for info in subpkg_info)
                modules_to_collect.extend(
                    subpkg_specs
                )

            if hasattr(module_spec, "loader"):
                source = module_spec.loader.get_source(module_spec.name)
            else:
                source = None

            # TODO: yield at the module/submodule/class/function level instead of the source file level?
            resource = Resource(uri=self.get_uri_for_location(module_spec.origin), content=source, metadata=metadata)
            resource.id = self.get_id_for_resource(resource)
            yield resource


    def load(self, uri: str):
        location = uri.removeprefix("file:")
        with open(location, 'r') as python_file:
            source = python_file.read()
        return source


# class RLangLoader(BaseCodeLoader):
#     def discover(self, locations: list[str], metadata: dict = None, *args, **kwargs):
#         return super().discover(locations, metadata, *args, **kwargs)

#     def load(self, location: str):
#         return super().load(location)


# class GithubLoader(BaseCodeLoader):
#     def discover(self, locations: list[str], metadata: dict = None, *args, **kwargs):
#         return super().discover(locations, metadata, *args, **kwargs)

#     def load(self, location: str):
#         return super().load(location)
