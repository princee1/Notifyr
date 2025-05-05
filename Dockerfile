FROM python:3.11-slim

#FROM python:3.11-alpine

RUN apt-get update && apt-get install -y make

# RUN apk add --no-cache make gcc musl-dev

RUN useradd -m celery

USER celery

WORKDIR /usr/src/

COPY ./assets ./assets/

COPY ./app ./app/

COPY ./requirements_dev.txt .

COPY ./Makefile .

COPY --chmod=755 ./scripts/spawn_celery_worker.sh ./spawn_celery_worker.sh

#RUN chmod +x ./spawn_celery_worker.sh

RUN make install

RUN pip show celery

ENV PATH="/home/celery/.local/bin:${PATH}"

#ENV PATH="/home/uvicorn/.local/bin:${PATH}"

RUN celery --version
