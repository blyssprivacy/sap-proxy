import numpy as np

from .pc import PineconeQuery, PineconeVector, PineconeProxy

D = 512

pcproxy = PineconeProxy(
    index_name="blysstest",
    dim=D,
    pinecone_api_key="e0a80619-a212-4d7f-95d4-ca67325d1ce5",
    data_key=b"\x00" * 32,
    beta=0.1,
    proxy_url="http://localhost:8081",
)


# Generate vectors that lie along the diagonal of the unit hypercube.
# Basic sanity test: neighbors in sequence id are also nearest neighbors in vector space.
N = 100
_magnitudes = np.arange(0, N, dtype=np.float32).reshape(N, 1)
_direction = np.ones((1, D), dtype=np.float32)
# [N, 1] @ [1, D] = [N, D]
np_vectors = _magnitudes @ _direction
# normalize by largest magnitude, so all vector lengths are in the range [0, 1]
np_vectors /= np.linalg.norm(np_vectors[-1])

vectors = [
    PineconeVector(
        id=str(i),
        values=np_vectors[i, :].tolist(),
        metadata={"arbitrary": "data"},
    ).model_dump(exclude_none=True)
    for i in range(N)
]

upsert = {"namespace": "default", "vectors": vectors}
r = pcproxy.client.post(f"{pcproxy.url}/vectors/upsert", json=upsert)
assert r.is_success

query = PineconeQuery(
    namespace="default",
    topK=3,
    values=vectors[0]["values"],
).model_dump(exclude_none=True)

r = pcproxy.client.post(f"{pcproxy.url}/query", json=query)
rj = r.json()
if "ciphermatches" in rj:
    print("Raw Results in encrypted space:")
    ciphermatches = [(m["id"], m["score"]) for m in rj["ciphermatches"]]
    print(ciphermatches)
    print("Filtered Results:")
    matches = [(m["id"], m["score"]) for m in rj["matches"]]
    print(matches)
