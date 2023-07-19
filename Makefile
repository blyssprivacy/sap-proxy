docker:
	docker build . -t blyss/proxy

docker-test: docker
	docker build . -t blyss/proxy-test -f ./config/Dockerfile.test

docker-prod:
	docker build . -t blyss/proxy-prod -f ./config/Dockerfile.prod

test-server: docker-test
	docker run -it --rm  --network=host --tmpfs /tmp --tmpfs /fakepersist blyss/proxy-test:latest

test-client:
	python -m src.test
