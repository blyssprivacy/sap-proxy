import json
import os
import sys

import numpy as np

from blyss_vectors import PineconeProxy

D = 512

# Pinecone API key must be for the us-east-1-aws environment!
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "exampleapikey")
proxy_url = sys.argv[1]

pcproxy = PineconeProxy(
    index_name="blysstest",
    dim=D,
    pinecone_api_key=PINECONE_API_KEY,
    data_key=b"\x00" * 32,
    proxy_url=proxy_url,
    beta=0.1,
)

# Generate vectors that lie along the diagonal of the unit hypercube.
# Basic sanity test: neighbors in sequence id will also be nearest neighbors in plaintext space.
N = 100
_magnitudes = np.arange(0, N, dtype=np.float32).reshape(N, 1)
_direction = np.ones((1, D), dtype=np.float32)
# [N, 1] @ [1, D] = [N, D]
np_vectors = _magnitudes @ _direction
# normalize by largest magnitude, so all vector lengths are in the range [0, 1]
np_vectors /= np.linalg.norm(np_vectors[-1])

# Prepare data for Pinecone's REST API
vectors = [
    {
        "id": str(i),
        "values": np_vectors[i, :].tolist(),
        "metadata": {"arbitrary": "data"},
    }
    for i in range(N)
]
# pcproxy.client is a httpx Client instance; near-identical API to the common "requests" Client
# need to explicitly include the data key from pcproxy
r = pcproxy.client.post(
    f"{pcproxy.url}/vectors/upsert",
    headers=pcproxy.secret,
    json={"namespace": "default", "vectors": vectors},
)
assert r.is_success


# We query for vector id 0, so will get items with indices near zero
query = {"namespace": "default", "topK": 3, "values": vectors[0]["values"]}

r = pcproxy.client.post(f"{pcproxy.url}/query", headers=pcproxy.secret, json=query)
rj = r.json()
if "ciphermatches" in rj:
    print("Raw Results in encrypted space:")
    ciphermatches = [(m["id"], m["score"]) for m in rj["ciphermatches"]]
    print(ciphermatches)
    print("Filtered Results:")
    matches = [(m["id"], m["score"]) for m in rj["matches"]]
    print(matches)
