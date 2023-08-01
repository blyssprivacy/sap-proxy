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
        dim: int,
        pinecone_api_key: str,
        data_key: bytes,
        proxy_url: str,
        beta: float = 0.0,
        region: str = "us-east1-aws",
    ):
        self.url = proxy_url
        self.index_name = index_name
        self.upstream_url = None
        self.dim = dim
        self.beta = beta
        self.region = region

        data_key_base64 = base64.b64encode(data_key).decode("utf8")
        self.secret = {"x-data-key": data_key_base64}

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
        # Setup the Pinecone index. Request is sent through the Blyss proxy transparently.
        r = self.client.get(f"{self.url}/databases")
        r.raise_for_status()
        pc_indices = r.json()
        if self.index_name not in pc_indices:
            print(f"Creating index {self.index_name}. May take minutes to be ready.")
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
        TIMEOUT = 180
        POLLWAIT = 5
        i = 0
        while i < TIMEOUT:
            r = self.client.get(f"{self.url}/databases/{self.index_name}")
            index_status = r.json()["status"]
            if index_status["ready"]:
                self.upstream_url = f"https://{index_status['host']}"
                break
            time.sleep(POLLWAIT)
            i += POLLWAIT
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
