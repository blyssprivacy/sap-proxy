docker:
	docker build . -t blyss/proxy

docker-prod: docker
	docker build . -t blyss/proxy-prod -f config/Dockerfile.prod

server-prod: docker-prod
	mkdir -p build
	nitro-cli build-enclave --docker-uri blyss/proxy-prod:latest --output-file build/proxy-prod.eif
	nitro-cli run-enclave --config config/nitro-config-prod.json

server-test: docker
	docker run -it --rm  --network=host blyss/proxy:latest /bin/bash /enclave/launch.sh 

client-test-local:
	cd client && pipenv run python test.py http://localhost:8081

client-test:
	cd client && pipenv run python test.py https://pcproxy.blyss.dev
