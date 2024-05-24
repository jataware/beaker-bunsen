import contextlib
import importlib
import importlib.util
import logging
import os
import pkgutil
import requests
import sys
import tarfile
import tempfile
from collections import deque, defaultdict
from pathlib import Path
from typing import Any

from .base import BaseLoader
from .schemes import LocalFileScheme, PythonModuleScheme, RCranScheme, read_from_uri
from . import schemes
from ..types import Default, DefaultType
from ..resources import Resource, CodeResource, ExampleResource, DocumentationResource

logger = logging.getLogger("beaker_bunsen")

class BaseCodeLoader(BaseLoader):

    Scheme = LocalFileScheme
    # URI_SCHEME = "file"

    def read(
            self,
            location: str,
            base: str = ""
        ):
        if location.startswith(self.Scheme.URI_SCHEME):
            uri = location
        else:
            uri = self.Scheme.get_uri_for_location(location, base)
        return read_from_uri(uri)


class PythonLibraryLoader(BaseCodeLoader):

    Scheme = PythonModuleScheme
    SLUG = "python"

    def discover(
        self,
        locations: list[str] | DefaultType = Default,
        metadata: dict | DefaultType = Default,
        exclusions: list[str] = Default,
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
        if locations is Default:
            locations = self.locations
        if metadata is Default:
            metadata = self.metadata
        if exclusions is Default:
            exclusions = self.exclusions

        # Update or define locations and exclusions based on '!' prefix in location.
        locations, parsed_exclusions = self.parse_locations(locations)
        exclusions.extend(parsed_exclusions)

        modules_to_collect = deque()
        for module_name in locations:
            module_spec = importlib.util.find_spec(module_name)
            if module_spec is None:
                raise ValueError(
                    f"Module '{module_name}' is not able to be imported. Please ensure that it is listed as a "
                    f"requirement and that 'require-runtime-dependencies' is enabled if error encountered during build."
                )
            modules_to_collect.append(module_spec)

        while modules_to_collect:
            module_spec = modules_to_collect.popleft()

            if not module_spec.origin.endswith('.py'):
                logger.info(f"Skipping importing non-python file {module_spec.origin}")
                continue

            if getattr(module_spec, "submodule_search_locations", []):
                subpkg_info: pkgutil.ModuleInfo = pkgutil.iter_modules(path=module_spec.submodule_search_locations)
                subpkg_specs = (info.module_finder.find_spec(f"{module_spec.name}.{info.name}") for info in subpkg_info)
                if self.exclusions:
                    subpkg_specs = (
                        spec for spec in subpkg_specs
                        if not self.should_exclude(spec.name)
                    )
                modules_to_collect.extend(
                    subpkg_specs
                )

            if hasattr(module_spec, "loader"):
                source = module_spec.loader.get_source(module_spec.name)
            else:
                source = None

            origin_path = Path(module_spec.origin)
            for sys_path in sys.path:
                if origin_path.is_relative_to(sys_path):
                    basedir = sys_path
                    break
            else:
                basedir = ""

            resource = CodeResource(
                uri=self.Scheme.get_uri_for_location(module_spec.name),
                content=source,
                metadata={
                    "package": module_spec.name,
                    "type": "code",
                    **metadata,
                }
                # basedir=basedir
            )
            resource.id = self.get_id_for_resource(resource)
            yield resource


class RCRANLocalCache(contextlib.AbstractContextManager):
    # Class attributes
    remote_package_cache: dict[str, dict[str, str]] = {}
    local_package_cache: dict[str, str] = {}
    tempdir_context_holder: dict[str, contextlib.AbstractContextManager] = {}
    ref_counts: dict[str, int] = defaultdict(lambda: 0)

    # Instance/context attributes
    repo: str
    context_locations: list[str]

    def __init__(self, locations: list[str], repo="https://cran.rstudio.com/src/contrib") -> None:
        self.repo = repo
        self.context_locations = locations
        if not self.remote_package_cache:
            self.build_package_cache()

    def __enter__(self) -> dict[str, str]:
        results = {}
        for location in self.context_locations:
            # Increase ref counter to reflect usage in new context
            self.__class__.ref_counts[location] += 1

            # Return the cached if it exists
            existing_cache = self.local_package_cache.get(location, None)
            if existing_cache and os.path.isdir(existing_cache):
                results[location] = existing_cache
                continue

            if '@' in location:
                package_name, version = location.split("@", maxsplit=1)
            else:
                package = self.remote_package_cache.get(location, None)
                if not package:
                    raise LookupError(f"Unable to find CRAN package name '{location}'")
                package_name = package["package"]
                version = package["version"]

            source_tarball_url = f"{self.repo}/{package_name}_{version}.tar.gz"
            tarball_req = requests.get(source_tarball_url, stream=True)

            context_mgr = tempfile.TemporaryDirectory()
            tmpdir = context_mgr.__enter__()
            results[location] = tmpdir
            self.tempdir_context_holder[location] = context_mgr
            self.local_package_cache[location] = tmpdir

            tar_file = tarfile.open(mode="r:gz", fileobj=tarball_req.raw)
            tar_file.extractall(path=tmpdir)
        return results

    def __exit__(self, exc_type, exc_value, traceback):
        # Update ref counts for local context
        for location in self.context_locations:
            self.__class__.ref_counts[location] -= 1
        # Clean up if there are no references
        locations_to_cleanup = [
            location
            for location, ref_count in self.__class__.ref_counts.items()
            if ref_count == 0
        ]
        for location in locations_to_cleanup:
            context_mgr = self.tempdir_context_holder[location]
            context_mgr.__exit__(exc_type, exc_value, traceback)
            del self.tempdir_context_holder[location]
            del self.local_package_cache[location]
            del self.__class__.ref_counts[location]
        return super().__exit__(exc_type, exc_value, traceback)

    def build_package_cache(self):
        package_page = f"{self.repo}/PACKAGES"
        package_req = requests.get(package_page)
        package_content = package_req.text
        packages = {}
        current_package = {}
        for line in package_content.splitlines():
            if line == "":
                packages[current_package["package"]] = current_package
                current_package = {}
                continue
            elif line.startswith("       "):
                current_package[label] += " " + line.lstrip()
                continue
            try:
                label, value = line.split(":", maxsplit=1)
                label = label.lower().strip()
                value = value.strip()
            except ValueError:
                raise
            current_package[label] = value
        self.remote_package_cache.clear()
        self.remote_package_cache.update(packages)


class RCRANSourceLoader(BaseCodeLoader):
    REPO: str = "https://cran.rstudio.com/src/contrib"
    SLUG: str = "rcran"

    Scheme = RCranScheme

    remote_package_cache: dict[str, Any] | None = {}
    local_package_cache: dict[str, str] | None = {}

    def __init__(
        self,
        locations: list[str] | None = None,
        metadata: dict | None = None,
        exclusions: list[str] | None = None
    ) -> None:
        super().__init__(locations, metadata, exclusions)

    def discover(
        self,
        locations: list[str] | DefaultType = Default,
        metadata: dict | DefaultType = Default,
        exclusions: list[str] = Default,
    ):
        """
        The `locations` should be R packages, as they are named in Cran with an option version number separated from the
        package name by an @ symbol.

        Example: locations=["purr", "jsonlite", "shiny@1.8.1", "leaflet@2.0"]
        """
        if locations is Default:
            locations = self.locations
        if metadata is Default:
            metadata = self.metadata
        if exclusions is Default:
            exclusions = self.exclusions

        # Update or define locations and exclusions based on '!' prefix in location.
        locations, parsed_exclusions = self.parse_locations(locations)
        exclusions.extend(parsed_exclusions)

        with RCRANLocalCache(locations=locations) as cache:
            for package_name, tempdir in cache.items():
                for dirpath, _dirnames, filenames in os.walk(top=tempdir):
                    for filename in filenames:
                        if filename.startswith('.'):
                            continue
                        full_path = Path(os.path.join(dirpath, filename))
                        if "R" in full_path.parts and full_path.suffix == ".R":
                            resource_type = CodeResource
                            location = str(full_path.relative_to(tempdir))
                        elif "vignettes" in full_path.parts and full_path.suffix.startswith(".R"):
                            resource_type = ExampleResource
                            location = str(full_path.relative_to(tempdir))
                        elif "man" in full_path.parts and full_path.suffix.startswith(".R"):
                            resource_type = DocumentationResource
                            location = str(full_path.relative_to(tempdir))
                        else:
                            continue

                        with open(full_path, 'r') as fh:
                            content = fh.read()
                            fh.seek(0)
                            resource = resource_type(
                                uri=self.Scheme.get_uri_for_location(
                                    base=package_name,
                                    location=location,
                                ),
                                file_handle=fh,
                                content=content,
                                metadata={
                                    "package": package_name,
                                    "path": str(full_path),
                                    "type": resource_type.resource_type.value,
                                    **metadata,
                                }
                            )
                            resource.id = self.get_id_for_resource(resource)
                            yield resource
