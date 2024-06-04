import importlib
import inspect
import json
import logging
import os.path
import pathlib
import pkgutil
import shutil
import sys
from copy import deepcopy
from typing import Any, Callable

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.plugin import hookimpl

from beaker_kernel.lib.context import BaseContext
from ..corpus.corpus import Corpus
from ..corpus.types import URI
from ..corpus.loaders.code_library_loader import RCRANLocalCache
from ..corpus.loaders.schemes import RCranScheme, unmap_scheme
from ..corpus.vector_stores.chromadb_store import ZippedChromaDBStore


logger = logging.getLogger("bunsen_build")


class BuildError(Exception):
    pass


class BuildConfigError(BuildError):
    pass


class BunsenConfig:
    _CONFIG_KEYS_TO_SAVE = [
        "documentation_paths",
        "examples_paths",
        "libraries",
    ]
    _CONFIG_KEYS_TO_IGNORE = [
        "require-runtime-dependencies",
    ]

    _build_config: dict[str, Any]
    locations: list[URI]

    library_descriptions: dict[str, str]
    libraries: dict[str, dict[str, list[str]]] = {}

    def library_extraction(obj: dict[str, dict[str, str]]) -> list[str]:
        locations = []
        for lang, entries in obj.items():
            scheme = unmap_scheme(lang)
            if scheme is None:
                raise BuildError("Unknown language added")
            locations.extend(f"{scheme.URI_SCHEME}:{location}" for location in entries.keys())
        return locations

    CONFIG_LOCATION_MAP: dict[str, Callable[[Any], list[str]]] = {
        "documentation_path": lambda obj: [f"documentation:{obj}"],
        "documentation_paths": lambda obj: [f"documentation:{loc}" for loc in obj],
        "examples_path": lambda obj: [f"examples:{obj}"],
        "examples_paths": lambda obj: [f"examples:{loc}" for loc in obj],
        "libraries": library_extraction,
    }


    def __init__(self, build_config: dict[str, Any]) -> None:

        if "documentation_path" in build_config and "documentation_paths" in build_config:
            raise BuildConfigError(f"Both 'documentation_path' and 'documentation_paths' defined. Only one can be defined at a time.")
        if "examples_path" in build_config and "examples_paths" in build_config:
            raise BuildConfigError(f"Both 'example_path' and 'example_paths' defined. Only one can be defined at a time.")

        self._build_config = deepcopy(build_config)
        self.locations = []

        for config_opt, transformer in self.CONFIG_LOCATION_MAP.items():
            if config_opt in build_config:
                config_value = build_config.get(config_opt)
                locations = transformer(config_value)
                uris = map(URI, locations)
                self.locations.extend(uris)

        self.locations.extend(map(URI, build_config.get("locations", [])))

    def to_json(self):
        config_dict = {
            key: value
            for key, value in self._build_config.items()
            if key in self._CONFIG_KEYS_TO_SAVE
        }
        missed_keys = set(self._build_config.keys()) - set(config_dict.keys()) - set(self._CONFIG_KEYS_TO_IGNORE)
        if missed_keys:
            missed_keys_str = "', '".join(missed_keys)
            logger.warning(f"Notice: Config option(s) '{missed_keys_str}' were defined but are not being used.")
        config_dict.update({
            "build_uris": self.locations,
        })

        # Fix up singular paths for consistency
        if "documentation_path" in config_dict:
            config_dict["documentation_paths"] = [config_dict.pop("documentation_path")]
        if "examples_path" in config_dict:
            config_dict["examples_paths"] = [config_dict.pop("examples_path")]

        return config_dict


class BunsenHook(BuildHookInterface):
    PLUGIN_NAME = "bunsen"
    _BUILD_DIR = "build"

    bunsen_config: BunsenConfig

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:

        self.bunsen_config = BunsenConfig(self.config)

        if "shared-data" not in build_data:
            build_data["shared_data"] = {}

        if self.target_name == "wheel":
            packages = self.build_config.packages

            # Build corpus, place as artifact
            # TODO: allow different contexts with different corpuses in one repo?
            corpus_path = self.build_corpus()
            for package_dir in packages:
                # Add package's parent directory to the python path so we can import the package
                sys.path.append(str(pathlib.Path(package_dir).parent))

                # TODO: check if context class exists. Only add corpus if proper context in package.
                context_slug, context_file_path = self.build_beaker_context(base_path=package_dir)
                if context_slug:
                    # Set to include the corpus
                    build_data["shared_data"][corpus_path] = f"share/beaker/corpuses/{context_slug}"

                    # Add beaker context json file(s)
                    build_data["shared_data"][context_file_path] = f"share/beaker/contexts/{context_slug}.json"

                bunsen_config_path =  os.path.join(self._BUILD_DIR, "bunsen_config.json")
                target = f"share/beaker/bunsen/{context_slug}.json"
                with open(bunsen_config_path, "w") as bunsen_config_file:
                    json.dump(self.bunsen_config.to_json(), bunsen_config_file)
                build_data["shared_data"][bunsen_config_path] = target


    def build_corpus(self) -> str:
        corpus_path = "build/corpus"
        store_path = "build/store.zip"

        if os.path.exists(corpus_path):
            shutil.rmtree(corpus_path)
        if os.path.exists(store_path):
            shutil.rmtree(store_path)

        os.makedirs(corpus_path, exist_ok=True)

        store = ZippedChromaDBStore(path=store_path)
        corpus = Corpus(store=store)

        cran_libs = [
            location.path
            for location in self.bunsen_config.locations
            if location.scheme == RCranScheme.URI_SCHEME
        ]
        with RCRANLocalCache(locations=cran_libs):
            corpus.ingest(
                self.bunsen_config.locations,
            )
            corpus.save_to_dir(corpus_path, overwrite=True)

        return corpus_path

    def build_beaker_context(self, base_path: str):

        dest_dir = "build/contexts"
        pkg_name = os.path.basename(base_path)

        slug = None
        class_name = None
        package = None

        for mod_info in pkgutil.walk_packages([base_path], prefix=f"{pkg_name}."):

            spec = mod_info.module_finder.find_spec(f"{mod_info.name}")
            mod = importlib.import_module(spec.name)

            for cls_name, cls in inspect.getmembers(mod, predicate=inspect.isclass):
                if issubclass(cls, BaseContext) and cls.__module__ == spec.name:
                    if slug:
                        raise ValueError("Can't define more than one context per package.")
                    slug = pkg_name
                    class_name = cls_name
                    package = spec.name

        if slug:
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = os.path.join(dest_dir, f"{slug}.json")
            context_file_contents = {
                "slug": slug,
                "package": package,
                "class_name": class_name,
            }
            with open(dest_file, "w") as context_file:
                json.dump(context_file_contents, context_file, indent=2)
            return slug, dest_file
        else:
            return None, None


    def test_examples(self, examples):
        # TODO: Finish this
        return []



@hookimpl
def hatch_register_build_hook():
    return BunsenHook
