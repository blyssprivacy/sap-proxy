# Pydantic models of the Pinecone API schemas

import base64
import time
from typing import Any, Optional

import httpx
import numpy as np
from pydantic import BaseModel

from .sap import sap, unsap


class PineconeBase(BaseModel):
    namespace: str


class PineconeVector(BaseModel):
    id: Optional[str] = None
    values: Optional[list[float]] = None
    metadata: Optional[dict[str, Any]] = None
    sparse_values: Optional[dict[str, list[int | float]]] = None

    def get_np(self) -> np.ndarray:
        if self.values is not None:
            return np.asarray(self.values, dtype=np.float32)
        elif self.sparse_values is not None:
            raise NotImplementedError("Sparse vectors are not yet supported.")
        else:
            raise ValueError("Didn't find any vector data.")

    def apply_sap(self, key: bytes, beta: float, nonce: bytes):
        plainvec = self.get_np()
        ciphervec = sap(key, plainvec, beta=beta, nonce=nonce)
        self.values = ciphervec.tolist()
        meta = self.metadata or {}
        meta.update({"nonce_b64": base64.b64encode(nonce).decode("utf8"), "beta": beta})
        self.metadata = meta

    def apply_unsap(self, key: bytes):
        if self.metadata is None:
            raise ValueError("Missing metadata.")
        ciphervec = self.get_np()
        nonce = base64.b64decode(self.metadata["nonce_b64"])
        plainvec = unsap(key, ciphervec, beta=self.metadata["beta"], nonce=nonce)
        self.values = plainvec.tolist()


class PineconeQuery(PineconeVector, PineconeBase):
    topK: int
    includeValues: bool = True
    includeMetadata: bool = True


class PineconeUpsert(PineconeBase):
    vectors: list[PineconeVector]


class PineconeResult(PineconeVector):
    score: float

    def rescore(self, query: PineconeVector):
        # compute euclidian distance to another vector
        self.score = (np.linalg.norm(self.get_np() - query.get_np())).item()


class PineconeProxy:
    def __init__(
        self,
        index_name: str,
        dim: int,
        pinecone_api_key: str,
        data_key: bytes,
        beta: float = 0.0,
        proxy_url: str = "http://localhost:8000",
    ):
        self.url = proxy_url
        self.index_name = index_name
        self.upstream_url = None
        self.dim = dim
        self.beta = beta
        data_key_base64 = base64.b64encode(data_key).decode("utf8")
        self.client = httpx.Client(
            headers={"Api-Key": pinecone_api_key, "x-data-key": data_key_base64}
        )

        self.init()

    def init(self):
        # 1. Setup the Pinecone index. Request is sent through the Blyss proxy transparently.
        pc_indices = self.client.get(f"{self.url}/databases").json()
        if self.index_name not in pc_indices:
            print(f"Creating index {self.index_name}")
            cfg = {
                "name": self.index_name,
                "dimension": self.dim,
                "metric": "euclidean",
                "pods": 1,
                "replicas": 1,
                "pod_type": "s1.x1",
            }
            r = self.client.post(f"{self.url}/databases", json=cfg)
            assert r.is_success

        # Pinecone assigns a unique hostname for each index.
        # Fetch index status and wait for ready.
        i = 0
        while i < 20:
            r = self.client.get(f"{self.url}/databases/{self.index_name}")
            index_status = r.json()["status"]
            if index_status["ready"]:
                self.upstream_url = f"https://{index_status['host']}"
                break
            time.sleep(1)
        assert self.upstream_url is not None

        # Proxy setup: point it to the live Pinecone server, and set the beta parameter.
        r = self.client.post(
            f"{self.url}/blyss/setup",
            json={"upstream": self.upstream_url, "beta": self.beta},
        )
        assert r.is_success

    def set_beta(self, beta: float):
        self.beta = beta
        r = self.client.post(
            f"{self.url}/blyss/setup",
            json={"upstream": self.upstream_url, "beta": self.beta},
        )
        assert r.is_success
