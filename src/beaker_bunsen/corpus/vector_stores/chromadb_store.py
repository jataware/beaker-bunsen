import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence, Callable
from typing_extensions import Self
from zipfile import ZipFile

import chromadb
from chromadb.api import ClientAPI

from ..types import Record, RecordBundle, QueryResponse, QueryResponse
from ..protocols import EmbeddingFunction
from .base_vector_store import VectorStore
from ..loaders.base import BaseLoader


class BaseChromaDBStore(VectorStore):
    client: ClientAPI
    default_partition: str

    _chromadb_get_include = ["documents", "metadatas", "uris"]
    _chromadb_query_include = _chromadb_get_include + ["distances",]

    def __init__(
            self,
            settings: dict|None,
            default_partition: str|None = None,
            default_embedding_function: EmbeddingFunction|None = None,
        ) -> None:
        if default_partition is None and settings:
            default_partition = settings.get("collection_name", "default")
        super().__init__(
            default_partition=default_partition,
            default_embedding_function=default_embedding_function,
            settings=settings,
        )

    @classmethod
    def wrap_data_loader(cls, data_loader: BaseLoader):
        def wrapped_loader(uris: Sequence[str]):
            result = []
            for uri in uris:
                result.append(data_loader.read(uri))
            return result
        return wrapped_loader

    @classmethod
    def parse_query_results(cls, queries, results):
        pared_results = {k: v for k, v in results.items() if v is not None}
        pared_keys = pared_results.keys()
        query_results = [dict(zip(pared_keys, row)) for row in zip(*pared_results.values())]
        formatted_response = []
        for query, result in zip(queries, query_results):
            parsed_result = cls.parse_results(result)
            distances = result["distances"]
            matches = [{"record": record, "distance": distance} for record, distance in zip(parsed_result, distances)]
            formatted_response.append({"query": query, "matches": matches})
        return formatted_response

    @classmethod
    def parse_results(cls, results):
        pared_results = {k: v for k, v in results.items() if v is not None}
        pared_keys = pared_results.keys()
        results = [dict(zip(pared_keys, row)) for row in zip(*pared_results.values())]
        records = [
            Record(
                id=result.get('ids', None),
                embedding=result.get('embeddings', None),
                content=result.get('documents', None),
                uri=result.get('uris', None),
                image=result.get('datas', None),
                metadata=result.get('metadatas', None),
            )
            for result in results
        ]
        return records

    @classmethod
    def _parse_bundle_to_columns(cls, bundle):
        # Break bundle in to separate lists for chromadb
        data_cols = {
            "id": [],
            "embedding": [],
            "metadata": [],
            "content": [],
            "image": [],
            "uri": [],
        }
        attrs_in_bundle = set(["id"])

        for record in bundle:
            attrs_in_bundle.update((key for key in data_cols.keys() if getattr(record, key, None) is not None))

        for record in bundle:
            for key in attrs_in_bundle:
                value = getattr(record, key, None)
                # ChromaDB has a validation check to ensure that metadata isn't an empty dict, so we have to replace empty dicts with None
                if key == "metadata" and isinstance(value, dict) and value == {}:
                    value = None
                data_cols[key].append(value)
        return data_cols



    def get_partitions(self) -> list[str]:
        return [collection.name for collection in self.client.list_collections()]

    def get_collection(self, partition=None, data_loader=None):
        if partition is None:
            partition = self.default_partition
        return self.client.get_or_create_collection(name=partition, data_loader=data_loader)

    def get_record(self, id: Any, partition: str | None = None, include_embeddings=False):
        result = self.get_records(ids=[id], partition=partition, include_embeddings=include_embeddings)
        if result:
            return result[0]
        else:
            return []

    def get_records(self, ids: Any, partition: str | None = None, include_embeddings=False):
        collection = self.get_collection(partition)
        include = self._chromadb_get_include[:]
        if include_embeddings:
            include += ["embeddings"]
        results = collection.get(ids=ids, include=include)
        records = self.parse_results(results)
        return records

    def get_all(self, partition: str | None = None, include_embeddings=False):
        collection = self.get_collection(partition)
        include = self._chromadb_get_include[:]
        if include_embeddings:
            include += ["embeddings"]
        results = collection.get(include=include)
        records = self.parse_results(results)
        return records

    def add_record(self, record: Record, partition: str | None = None):
        collection = self.get_collection(partition)
        collection.add(
            ids=[record.id],
            embeddings=record.embedding and [record.embedding] or None,
            metadatas=record.metadata and [record.metadata,] or None,
            documents=record.content and [record.content,] or None,
            images=record.image and [record.image,] or None,
            uris=record.uri and [record.uri] or None,
        )

    def add_records(self, bundle: Sequence[Record], partition: str | None = None, data_loader: Callable|None=None):
        if not bundle:
            return

        collection = self.get_collection(partition, data_loader=self.wrap_data_loader(data_loader))

        data_cols = self._parse_bundle_to_columns(bundle)

        collection.add(
            ids = data_cols["id"],
            embeddings = data_cols["embedding"] or None,
            metadatas = data_cols["metadata"] or None,
            documents = data_cols["content"] or None,
            images = data_cols["image"] or None,
            uris = data_cols["uri"] or None,
        )

    def update_record(
        self,
        record: Record,
        partition: str|None = None
    ):
        self.update_records(bundle=[record], partition=partition)

    def update_records(
        self,
        bundle: RecordBundle,
        partition: str|None = None
    ):
        collection = self.get_collection(partition)
        data_cols = self._parse_bundle_to_columns(bundle)
        collection.update(
            ids = data_cols["id"],
            embeddings = data_cols["embedding"] or None,
            metadatas = data_cols["metadata"] or None,
            documents = data_cols["content"] or None,
            images = data_cols["image"] or None,
            uris = data_cols["uri"] or None,
        )


    def query(
        self,
        query_string: str,
        partition: str | None = None,
        limit: int = -1,
        include_embeddings: bool = False,
    ) -> QueryResponse:
        if not isinstance(query_string, str):
            raise ValueError(f"Argument `query_string` expected to be of type 'string'.")
        results = self.query_multi(query_strings=[query_string], partition=partition, limit=limit, include_embeddings=include_embeddings)
        if results:
            return results[0]
        else:
            return []

    def query_multi(
        self,
        query_strings: list[str],
        partition: str | None = None,
        limit: int = -1,
        include_embeddings: bool = False,
    ) -> Sequence[QueryResponse]:
        kwargs = {}
        if isinstance(limit, int) and limit > 0:
            kwargs["n_results"] = limit

        if not isinstance(query_strings, (list, tuple, set)):
            raise ValueError(f"Argument `query_strings` expected to be a sequence containing type 'string'.")
        include = self._chromadb_query_include[:]
        if include_embeddings:
            include += ["embeddings"]
        collection = self.get_collection(partition)
        response = collection.query(query_texts=query_strings, include=include, **kwargs)
        results = self.parse_query_results(query_strings, response)
        return results

    def clone(
            self,
            **kwargs,
        ) -> Self:
        clone = self.__class__(**kwargs)
        return clone

    def save_to(
        self,
        destination: str | Path,
    ) -> str:
        source = getattr(self.client, '_identifier', None)
        if not isinstance(destination, Path):
            destination = Path(destination)
        if not destination.parent.exists():
            destination.parent.mkdir(parents=True)

        if destination.exists():
            if destination.is_dir():
                destination = destination / "store"
            else:
                raise FileExistsError("Unable to save store as destination already exists.")

        shutil.copytree(source, destination, dirs_exist_ok=False)
        return str(destination)


class ChromaDBLocalStore(BaseChromaDBStore):
    def __init__(
        self,
        path: str,
        settings: dict|None = None,
        default_partition: str|None = None,
        default_embedding_function: EmbeddingFunction|None = None,
    ):
        self.client = chromadb.PersistentClient(path=path)
        super().__init__(
            settings=settings,
            default_partition=default_partition,
            default_embedding_function=default_embedding_function,
        )

    def clone(self, path=None, **kwargs) -> Self:
        if path is None:
            path = Path(tempfile.mkdtemp())
        if not path.is_dir:
            path.mkdir(parents=True)
        client_path = getattr(self.client, '_identifier', None)
        if not client_path:
            raise ValueError("Unable to locate path to existing store")
        client_path = Path(client_path)
        shutil.copytree(client_path, path, dirs_exist_ok=True)
        return ChromaDBLocalStore(
            str(path),
            settings=self.store_settings,
            default_embedding_function=self.default_embedding_function,
            default_partition=self.default_partition
        )


class ChromaDBServerStore(BaseChromaDBStore):
    def __init__(
        self,
        host: str,
        port: str|int,
        settings: dict|None = None,
        default_partition: str|None = None,
        default_embedding_function: EmbeddingFunction|None = None,
    ):
        self.client = chromadb.HttpClient(host=host, port=port)
        super().__init__(
            settings=settings,
            default_partition=default_partition,
            default_embedding_function=default_embedding_function,
        )


class ZippedChromaDBStore(ChromaDBLocalStore):
    zipfile: str
    tempdir: str

    def __init__(
        self,
        path: str,
        settings: dict|None = None,
        default_partition: str|None = None,
        default_embedding_function: EmbeddingFunction|None = None,
    ):
        self.zipfile = path
        self.tempdir = tempfile.mkdtemp()
        local_store_path = os.path.join(self.tempdir, "store")

        os.makedirs(local_store_path)

        if os.path.isfile(path):
            with ZipFile(path) as zipped_store:
                zipped_store.extractall(local_store_path)

        super().__init__(
            path=local_store_path,
            settings=settings,
            default_partition=default_partition,
            default_embedding_function=default_embedding_function,
        )

    def clone(
        self,
        path=None,
        tempdir=None
    ) -> Self:
        clone = self.__new__(self.__class__)

        if tempdir is None:
            tempdir = Path(tempfile.mkdtemp())

        if path is None:
            path = self.zipfile

        clone.zipfile = path
        clone.tempdir = tempdir
        clone_store_dir = tempdir / "store"

        source_store_path = os.path.join(self.tempdir, "store")
        shutil.copytree(source_store_path, clone_store_dir, dirs_exist_ok=True)

        super(clone.__class__, clone).__init__(
            path=str(clone_store_dir),
            settings=self.store_settings,
            default_embedding_function=self.default_embedding_function,
            default_partition=self.default_partition,
        )
        return clone

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        if self.tempdir and os.path.exists(self.tempdir):
            shutil.rmtree(self.tempdir)

    @classmethod
    def from_localstore(cls, localstore: ChromaDBLocalStore, zipfile: str) -> Self:
        self = cls.__new__(cls)
        self.zipfile = zipfile
        self.tempdir = None

        # Copy state from the provided localstore
        self.__dict__.update(localstore.__dict__)

        return self

    def update_zipfile(self, zipfile: str | None = None):
        client_path = getattr(self.client, '_identifier', None)
        if not client_path:
            raise LookupError('Unable to lookup chromadb path')
        if zipfile is None:
            zipfile = self.zipfile
        with ZipFile(zipfile, 'w') as zipped_store:
            for (dirpath, _, files ) in os.walk(client_path):
                dirpath: str
                for file in files:
                    arcpath = os.path.join(dirpath.removeprefix(client_path), file).lstrip('/')
                    filepath = os.path.join(dirpath, file)
                    zipped_store.write(filename=filepath, arcname=arcpath)

    def save_to(
        self,
        destination: str | Path,
    ) -> str:
        if not isinstance(destination, Path):
            destination = Path(str)

        if not destination.parent.exists():
            destination.parent.mkdir(parents=True)

        if destination.exists():
            if destination.is_dir():
                destination = destination / "store.zip"

        if not destination.name.endswith(".zip"):
            raise ValueError("ZippedVectorStore instances can only be saved to files ending in the extension .zip")

        self.update_zipfile(zipfile=destination)
        return str(destination)
