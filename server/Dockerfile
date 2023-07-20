ARG HASH_NITRIDING=6dcfbf12d246f70103641d69a3a905b9f49328a9
ARG HASH_PYTHON=3b05edefacf62260bc0c572aa7cb871c87052e04661d2538b1b57672a87d8041

FROM golang:1.20 as n3-builder

WORKDIR /
RUN git clone https://github.com/brave/nitriding-daemon.git
RUN cd nitriding-daemon && git checkout $HASH_NITRIDING && \
		CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -buildvcs=false -o nitriding



FROM python:3.10@sha256:$HASH_PYTHON 

WORKDIR /enclave
COPY --from=n3-builder /nitriding-daemon/nitriding .

# pipenv creates its own venv, so it is fine to force-install it globally
RUN pip install pipenv --break-system-package
COPY Pipfile.lock .
ENV PIPENV_VENV_IN_PROJECT=1
RUN pipenv sync
ENV PATH="/enclave/.venv/bin:$PATH"

COPY server server/
COPY config/launch.sh .