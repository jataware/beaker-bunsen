import os.path
import shutil
import tempfile
import yaml
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Type
from typing_extensions import Self

from .vector_stores.chromadb_store import ChromaDBLocalStore, ZippedChromaDBStore
from .vector_stores.base_vector_store import VectorStore
from .loaders import BaseLoader, BaseCodeLoader, LocalFileLoader, PythonLibraryLoader
from .loaders.schemes import read_from_uri, CorpusResourceScheme
from .embedders import BaseEmbedder, DocumentationEmbedder
from .types import (
    Record, Embedding, Image, Metadata, QueryResponse, QueryResult, RecordBundle,
    DefaultType, Default, URI,
)
from .protocols import EmbeddingFunction
from .resources import Resource
from .util.helpers import common_path_portion


class Corpus:
    """
    A corpus is a single, self-contained interface for querying over documents and other records embedded in a vector database.
    """
    embedder_map: dict[str, BaseEmbedder]

    store: VectorStore
    default_embedding_function: EmbeddingFunction | None
    resource_location: str | None

    def __init__(
            self,
            store: VectorStore,
            default_embedding_function: EmbeddingFunction | None = None,
    ) -> None:
        self.store = store
        self.default_embedding_function = default_embedding_function

    @classmethod
    def from_zip(cls, zipfile_path: str | Path) -> Self:

        # instance = cls(store, default_embedding_function=default_embedding_function)
        # instance.resource_location = str(zipfile_path)
        pass

    @classmethod
    def from_dir(cls, dir_path: str | Path) -> Self:
        if not isinstance(dir_path, Path):
            dir_path = Path(dir_path)

        config_path = dir_path / "config.yaml"
        store_path = dir_path / "store.zip"
        resource_dir = dir_path / "resources"


        with config_path.open() as config_file:
            config = yaml.safe_load(config_file)

        if not dir_path.is_dir():
            raise FileNotFoundError(f"Provided corpus directory `{dir_path}` does not exist or is invalid.")
        if not (config_path.is_file() and store_path.is_file() and resource_dir.is_dir()):
            raise FileNotFoundError(f"Corpus is corrupt or missing required files and cannot be loaded.")

        store_config = config.get("store", {})
        if "default_embedding_function" in store_config:
            print("config", store_config)
            func = EmbeddingFunction.from_uri(store_config["default_embedding_function"])
            store_config["default_embedding_function"] = func
        store = ZippedChromaDBStore(
            path=store_path,
            **store_config
        )
        default_embedding_function = EmbeddingFunction.from_uri(config.get("default_embedding_function", None))

        instance = cls(store, default_embedding_function=default_embedding_function)
        instance.resource_location = str(resource_dir)
        return instance

    def ingest(
            self,
            embedder_cls: Type[BaseEmbedder],
            loader: BaseLoader | DefaultType = Default,
            base_metadata: dict | DefaultType = Default,
            partition: str | DefaultType = Default,
            embedding_function: EmbeddingFunction | DefaultType = Default,
            batch_size: int | DefaultType = Default,
    ):
        if base_metadata is Default:
            base_metadata = {}

        optional_kwargs = {}
        if partition is not Default:
            optional_kwargs["partition"] = partition

        if embedding_function is Default:
            embedding_function = self.default_embedding_function
        if embedding_function not in (Default, None):
            optional_kwargs["embedding_function"] = embedding_function

        if batch_size is not Default:
            optional_kwargs["batch_size"] = batch_size

        embedder = embedder_cls(store=self.store)
        embedder.ingest(loader=loader, metadata=base_metadata, **optional_kwargs)

    def save_to_dir(self, save_dir: str|Path, overwrite: bool = False):
        print(f"Saving to `{save_dir}`")
        if not isinstance(save_dir, Path):
            save_dir = Path(save_dir)
        if save_dir.exists():
            if not save_dir.is_dir():
                raise FileExistsError("Save destination `{save_dir}` already exists and is not a directory")
            has_contents = bool(next(save_dir.iterdir(), False))
            if has_contents:
                if not overwrite:
                    raise FileExistsError("Save destination `{save_dir}` is not empty and overwrite is set to False")
                else:
                    shutil.rmtree(save_dir)
                    save_dir.mkdir()

        store_zipfile = save_dir / "store.zip"
        config_file = save_dir / "config.yaml"
        resource_dir = save_dir / "resources"
        resource_dir.mkdir(parents=True)

        temp_store = self.store.clone()

        partitions = self.store.get_partitions()
        default_partition = self.store.default_partition
        default_store_embedding_function = self.store.default_embedding_function
        store_config = {
            "corpus": {
                EmbeddingFunction.get_uri(self.default_embedding_function),
            },
            "store": {
                "settings": self.store.store_settings,
                "default_partition": default_partition,
                "default_embedding_function": EmbeddingFunction.get_uri(default_store_embedding_function),
            }
        }
        with open(config_file, 'w') as store_config_fp:
            yaml.safe_dump(store_config, store_config_fp)

        resources: dict[str, set[str]] = {
            partition: set([]) for partition in partitions
        }
        records_to_update_by_partition: dict[str, list[Record]] = {
            partition: [] for partition in partitions
        }
        for partition in partitions:
            for record in temp_store.get_all(partition=partition, include_embeddings=True):
                if record.uri:
                    resources[partition].add(record.uri)
                    records_to_update_by_partition[partition].append(record)

        partition_common_paths = {
            partition: common_path_portion([
                uri.path
                for uri in resources[partition]
                if uri.startswith(("file:", "zipped-file:"))
            ])
            for partition in partitions
        }

        uri_remap = {}
        for (partition, resource_set) in resources.items():
            for resource_uri in resource_set:
                if resource_uri.scheme in ("file", "zipped-file"):
                    uri_path = Path(resource_uri.path).relative_to(partition_common_paths[partition])
                else:
                    uri_path = Path(resource_uri.path)

                resource_path = Path(partition) / uri_path
                new_uri = CorpusResourceScheme.get_uri_for_location(resource_path)
                content = read_from_uri(resource_uri)
                mode = "wb" if isinstance(content, bytes) else "w"
                dest = resource_dir / resource_path
                if not dest.parent.exists():
                    dest.parent.mkdir(parents=True)
                with open(dest, mode) as fh:
                    fh.write(content)
                uri_remap[resource_uri] = new_uri

        for partition, record_set in records_to_update_by_partition.items():
            for record in record_set:
                if record.uri not in uri_remap:
                    raise ValueError(f"Record that needs to be moved not moved?: {record.uri}")
                record.uri = uri_remap[record.uri]
            temp_store.update_records(record_set, partition=partition)
        temp_store.save_to(destination=store_zipfile)


    def save_to_zip(self, zipfile_path: str | Path, overwrite: bool = False):
        if not isinstance(zipfile_path, Path):
            zipfile_path = Path(zipfile_path)

        if zipfile_path.is_dir():
            zipfile_path = zipfile_path / "corpus.zip"

        if zipfile_path.exists() and not overwrite:
            raise FileExistsError(f"File `{zipfile_path}` already exists and overwrite is set to False.")

        save_dir = zipfile_path.parent
        if not save_dir.exists():
            raise FileNotFoundError("Unable to save zip as target directory does not exist.")

        tmpdir = tempfile.mkdtemp()
        try:
            self.save_to_dir(tmpdir)

            with zipfile.ZipFile(zipfile_path, "w") as corpus_zipfile:
                for (dirpath, _, files ) in os.walk(tmpdir):
                    dirpath: str
                    for file in files:
                        arcpath = os.path.join(dirpath.removeprefix(tmpdir), file).lstrip('/')
                        filepath = os.path.join(dirpath, file)
                        corpus_zipfile.write(filename=filepath, arcname=arcpath)
        finally:
            shutil.rmtree(tmpdir)

    def read_resource(self, location_or_uri: str):
        uri = URI(location_or_uri)
        # parsed_uri = urlparse(str(location_or_uri))
        if uri.scheme and uri.scheme != CorpusResourceScheme.URI_SCHEME:
            return read_from_uri(location_or_uri)

        resource_location = uri.path.lstrip("/")
        full_resource_path = Path(self.resource_location) / resource_location
        with full_resource_path.open() as resource_fp:
            content = resource_fp.read()
        return content

    def query(self,
        query_string: str,
        partition: str | None = None,
        limit: int = -1,
        **kwargs
    ):
        self.store.query(
            query_string=query_string,
            partition=partition,
            limit=limit,
            **kwargs,
        )
