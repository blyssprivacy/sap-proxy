-include .env
export

docker:
	docker build server -t blyss/proxy

docker-prod: docker
	docker build server -t blyss/proxy-prod -f server/Dockerfile.prod

server-prod: docker-prod
	mkdir -p build
	nitro-cli build-enclave --docker-uri blyss/proxy-prod:latest --output-file build/proxy-prod.eif
	nitro-cli run-enclave --config config/nitro-config-prod.json

server-test: docker
	docker run -it --rm  --network=host blyss/proxy:latest /bin/bash /enclave/launch.sh 


client/venv/bin/activate: client/pyproject.toml
	python3 -m venv client/venv
	./client/venv/bin/pip install -e ./client

client-test-local: client/venv/bin/activate
	./client/venv/bin/python client/test/basic.py http://localhost:8081

client-test: client/venv/bin/activate
	./client/venv/bin/python client/test/basic.py https://pcproxy.blyss.dev

