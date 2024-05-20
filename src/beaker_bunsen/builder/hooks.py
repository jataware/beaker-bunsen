import importlib
import inspect
import json
import logging
import os.path
import pathlib
import pkgutil
import shutil
import sys
from typing import Any

from hatchling.builders.config import BuilderConfig
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.plugin import hookimpl

from beaker_kernel.lib.context import BaseContext
from ..vectordb.embedders import DocumentationEmbedder, ExampleEmbedder, CodeEmbedder, PythonEmbedder
from ..vectordb.loaders import LocalFileLoader, PythonLibraryLoader, RCRANSourceLoader
from ..vectordb.loaders.code_library_loader import RCRANLocalCache
from ..vectordb.chromadb_store import ZippedChromaDBStore
from ..corpus import Corpus


logger = logging.getLogger("bunsen_build")

class BuildError(Exception):
    pass


class BunsenHook(BuildHookInterface):
    PLUGIN_NAME = "bunsen"

    _BUILD_DIR = "build"
    _CONFIG_KEYS_TO_SAVE = [
        "documentation_path",
        "examples_path",
        "python_libraries",
        "r_cran_libraries",
        "library_descriptions",
    ]
    _CONFIG_KEYS_TO_IGNORE = [
        "require-runtime-dependencies",
    ]

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:

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

                # TODO: Do we need to filter like this? Should we just filter out the most common build options and
                # include everything else?
                bunsen_config = {
                    key: value
                    for key, value in self.config.items()
                    if key in self._CONFIG_KEYS_TO_SAVE
                }
                missed_keys = set(self.config.keys()) - set(bunsen_config.keys()) - set(self._CONFIG_KEYS_TO_IGNORE)
                if missed_keys:
                    missed_keys_str = "', '".join(missed_keys)
                    logger.warning(f"Notice: Config option(s) '{missed_keys_str}' were defined but are not being used.")

                bunsen_config_path =  os.path.join(self._BUILD_DIR, "bunsen_config.json")
                target = f"share/beaker/bunsen/{context_slug}.json"
                with open(bunsen_config_path, "w") as bunsen_config_file:
                    json.dump(bunsen_config, bunsen_config_file)
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

        documentation_path = self.config.get("documentation_path", "documentation")
        examples_path = self.config.get("examples_path", "examples")
        python_libraries = self.config.get("python_libraries", [])
        r_cran_libraries = self.config.get("r_cran_libraries", [])

        if documentation_path and os.path.exists(documentation_path):
            corpus.ingest(
                embedder_cls=DocumentationEmbedder,
                loader=LocalFileLoader(locations=[documentation_path]),
                partition="documentation",
            )

        if examples_path and os.path.exists(examples_path):
            corpus.ingest(
                embedder_cls=ExampleEmbedder,
                loader=LocalFileLoader(locations=[examples_path]),
                partition="examples",
            )

        if python_libraries:
            corpus.ingest(
                embedder_cls=PythonEmbedder,
                loader=PythonLibraryLoader(locations=python_libraries, metadata={"language": "python"}),
                partition="code"
            )

        if r_cran_libraries:
            with RCRANLocalCache(locations=r_cran_libraries):
                corpus.ingest(
                    embedder_cls=CodeEmbedder,
                    loader=RCRANSourceLoader(locations=r_cran_libraries, metadata={"language": "r"}),
                    partition="code",
                )

        examples = corpus.store.get_all(partition="examples")
        if examples:
            failures = self.test_examples(examples)
            if failures and not self.config.get("ignore_example_errors", False):
                # TODO: Finish this
                # TODO: Should example testing just be in the ExampleEmbedder durring embedding instead of here?
                print("These examples failed")
                print(failures)
                raise BuildError("Example test failed and not ignored.")

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
