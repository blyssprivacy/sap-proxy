from typing import Any, Optional
import base64
import time
import secrets

import httpx

from .attest import verify_attestation_doc


class PineconeProxy:
    def __init__(
        self,
        index_name: str,
        pinecone_api_key: str,
        pinecone_region: str,
        secret_key: bytes,
        proxy_url: str,
        beta: float = 0.0,
        dim: Optional[int] = None,
    ):
        self.url = proxy_url
        self.index_name = index_name
        self.upstream_url = None
        self.dim = dim
        self.beta = beta
        self.controller_url = f"https://controller.{pinecone_region}.pinecone.io"

        secret_key_base64 = base64.b64encode(secret_key).decode("utf8")
        self.secret = {"x-data-key": secret_key_base64}

        self.client = httpx.Client(
            headers={"Api-Key": pinecone_api_key},
            verify=("localhost" not in proxy_url),
        )

        self.init()
        try:
            self.check_attestation()
        except Exception as e:
            print(f"WARNING: Attestation failed: {e}")

    def init(self):
        # Setup the Pinecone index. Request is sent directly to Pinecone.
        r = self.client.get(f"{self.controller_url}/databases")
        r.raise_for_status()
        pc_indices = r.json()

        # Convenience: create index if it doesn't exist. Recommend creation ahead of time; this is slow.
        if self.index_name not in pc_indices:
            print(f"Creating index {self.index_name}. May take minutes to be ready.")
            assert self.dim is not None, "Must specify dimension to create new index."
            cfg = {
                "name": self.index_name,
                "dimension": self.dim,
                "metric": "euclidean",
                "pods": 1,
                "replicas": 1,
                "pod_type": "s1.x1",
            }
            r = self.client.post(f"{self.controller_url}/databases", json=cfg)
            assert r.is_success

        # Pinecone assigns a unique hostname for each index.
        # Fetch index status and wait for ready.
        TIMEOUT = 180
        POLLWAIT = 5
        i = 0
        while i < TIMEOUT:
            r = self.client.get(f"{self.controller_url}/databases/{self.index_name}")
            index_status = r.json()["status"]
            if index_status["ready"]:
                self.upstream_url = f"https://{index_status['host']}"
                break
            time.sleep(POLLWAIT)
            i += POLLWAIT
        assert self.upstream_url is not None, "Timed out waiting for Pinecone index."

        # Proxy setup: point it to the live Pinecone index server, and set the beta parameter.
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

    def check_attestation(self):
        nonce = secrets.token_hex(16)
        r = self.client.get(f"{self.url}/enclave/attestation?nonce={nonce}")
        attestation_doc = base64.b64decode(r.content.decode("utf-8"))
        document_public_key, attested_pcrs = verify_attestation_doc(
            attestation_doc, None, None
        )
        if document_public_key is not None:
            print(document_public_key.hex())
        else:
            # TODO: enforce attestation; refuse to connect if PCRs don't match expectation
            # needs some way of published blessed PCRs
            for i, pcr in attested_pcrs.items():
                print(f"PCR{i}: {pcr.hex()}")
