cd /enclave
uvicorn server.proxy:app --host 127.0.0.1 --port 8081 --log-level debug
