import base64
import json
import secrets
from typing import Annotated, Any, Optional

import httpx
from fastapi import Body, FastAPI, Header, Request, Response

from .sap import NONCE_LENGTH
from .pc import PineconeQuery, PineconeResult, PineconeUpsert

app = FastAPI()

PINECONE_CONTROLLER_URL = "https://controller.us-east-1-aws.pinecone.io"
UPSTREAM_URL = "https://example.com"
BETA = 0.1


DataKey = Annotated[
    str, Header(..., alias="x-data-key", description="The data key, encoded as base64.")
]


@app.post("/blyss/setup")
async def set_upstream(
    upstream: Annotated[
        str,
        Body(
            description=(
                "The upstream database server to which requests will be proxied. "
                "Must be a valid URL."
            ),
        ),
    ],
    beta: Annotated[
        float,
        Body(
            description=(
                "The SAP beta parameter. "
                "Larger beta increases security (i.e. harder to recover plainvec from ciphervec) "
                "at the cost of less-accurate distance comparisons in the encrypted space. "
            ),
        ),
    ] = 0.0,
):
    global UPSTREAM_URL, BETA
    UPSTREAM_URL = upstream
    BETA = beta
    print(f"UPSTREAM_URL set to {UPSTREAM_URL}")
    print(f"BETA set to {BETA}")


async def forward_to_upstream(
    path: str,
    request: Request,
    new_body: Optional[bytes] = None,
    upstream: Optional[str] = None,
    **kwargs,
):
    # get a copy of the original headers, made mutable
    headers = dict(**request.headers)
    # strip the data key
    headers.pop("x-data-key", None)
    # strip content-length header (httpx will recompute)
    headers.pop("content-length", None)
    # strip host header (currently points to proxy)
    headers.pop("host", None)

    if "json" in kwargs:
        data = json.dumps(kwargs["json"]).encode("utf-8")
    else:
        data = new_body or await request.body()

    upstream_endpoint = f"{upstream or UPSTREAM_URL}/{path}"
    # print(f"forwarding to {upstream_endpoint}")
    async with httpx.AsyncClient() as client:
        # send the request to the upstream server
        fwd_request = httpx.Request(
            method=request.method, url=upstream_endpoint, content=data, headers=headers
        )
        response = await client.send(fwd_request)

    return response


@app.post("/query")
async def query(
    request: Request,
    plainquery: Annotated[
        PineconeQuery,
        Body(
            description=(
                "Pinecone query request, following https://docs.pinecone.io/reference/query."
            ),
        ),
    ],
    data_key: DataKey,
):
    if plainquery.id:
        # no change for id-based queries, passthrough
        return await forward_to_upstream(
            "query",
            request,
        )

    # apply SAP to plaintext query
    key = base64.b64decode(data_key)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    cipherquery = PineconeQuery(**plainquery.dict())
    cipherquery.apply_sap(key, beta=BETA, nonce=nonce)
    # force query params to allow effective unSAP
    cipherquery.includeValues = True
    cipherquery.includeMetadata = True
    cipherquery.topK = plainquery.topK * 3

    # rename values to vector; Pinecone uses inconsistent naming between query and upsert
    cipherquery_json = cipherquery.dict(exclude_none=True)
    cipherquery_json["vector"] = cipherquery_json.pop("values")

    response = await forward_to_upstream("query", request, json=cipherquery_json)

    # apply unsap to each vector in matches
    rj = response.json()
    matches = [PineconeResult(**m) for m in rj["matches"]]

    # snapshot the ciphermatches, for debugging
    ciphermatches = [m.dict(exclude_none=True) for m in matches]

    for m in matches:
        m.apply_unsap(key)
        # rescore the matches by computing distances in the plaintext space
        m.rescore(plainquery)

    filtered_matches = sorted(matches, key=lambda m: m.score)[: plainquery.topK]

    return {"matches": filtered_matches, "ciphermatches": ciphermatches}


@app.post("/vectors/upsert")
async def upsert(
    request: Request,
    upsert: Annotated[
        PineconeUpsert,
        Body(
            description=(
                "Pinecone upsert request, following https://docs.pinecone.io/reference/upsert."
            ),
        ),
    ],
    data_key: DataKey,
):
    key = base64.b64decode(data_key)
    for v in upsert.vectors:
        # apply SAP
        nonce = secrets.token_bytes(NONCE_LENGTH)
        v.apply_sap(key, beta=BETA, nonce=nonce)

    pcresponse = await forward_to_upstream(
        "vectors/upsert", request, json=upsert.dict(exclude_none=True)
    )

    return Response(
        content=pcresponse.content,
        status_code=pcresponse.status_code,
        headers=dict(pcresponse.headers),
    )


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    # if first path component is "databases", forward to Pinecone controller
    upstream = UPSTREAM_URL
    if path.startswith("databases"):
        upstream = PINECONE_CONTROLLER_URL

    response = await forward_to_upstream(path, request, upstream=upstream)

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
    )
