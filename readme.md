# Pinecone Proxy

## Client Quickstart
1. Install Python 3.10, and `pip install pipenv`
3. Get Pinecone API key (must be for region us-east-1-aws), paste it into client/test.py
4. From the `client` directory, `pipenv run python test.py https://pcproxy.blyss.dev`. This will connect to the proxy instance running inside a Blyss-managed enclave, display the attested enclave measurements, and perform some basic testing of the shuffle-and-perturb algorithm.

## Local development and testing
`make server-test` will run the proxy server locally via Docker. The local server does not support TLS, and listens on port 8081. Enclave-related features such as attestation are disabled.
This is an interactive command, so server logs will be printed to the terminal and the server will stop on Ctrl-C.

With the local server running, `make client-test-local` will run the client test script against localhost.

## Deployment
The production server requires TLS connections, and uses Let's Encrypt for certificate management. Make sure that the fully-qualified domain name for the server is pointing to the server's IP address, and modify `config/Dockerfile.prod` to include this FQDN.
`make server-prod` will build an enclave image file, then run it according to the enclave configuration (num CPUs, RAM allocation) in `config/nitro-config-prod.json`. The server will listen on port 443, and will accept TLS connections from any IP (non-TLS is not supported). On boot, the enclave will request a new certificate from Let's Encrypt. The server will run in the background, and no logs will be produced. Halt the server with `nitro-cli terminate-enclave --all`.

# Security model

The goal of this proxy is to obscure user data from a database provider, while still relying on the database service to perform efficient, accurate searches over large datasets. User data is not encrypted in any cryptographic sense; many semantic properties are preserved in the ciphertext, eventually leaking the plaintext after sufficient observation. More detailed  We implement the "scale-and-perturb" algorithm described by [Fuchsbauer et. al](https://eprint.iacr.org/2021/1666) as our obscuring transformation. The algorithm is parameterized by a "beta" parameter, which controls the amount of noise added to the data. Higher beta values make it more difficult to recover plaintext from ciphertext, at the cost of reduced search accuracy.
