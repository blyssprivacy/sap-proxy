# Pydantic models of the Pinecone API schemas

import base64
from typing import Any, Optional

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

