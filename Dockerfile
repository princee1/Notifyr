FROM python:3.11-slim

RUN apt-get update && apt-get install -y make

RUN useradd -m celery

USER celery

WORKDIR /usr/src/

COPY ./app ./app/

COPY ./requirements_dev.txt .

COPY ./Makefile .

COPY --chmod=755 ./scripts/spawn_celery_worker.sh ./spawn_celery_worker.sh

#RUN chmod +x ./spawn_celery_worker.sh

RUN make install

RUN pip show celery

ENV PATH="/home/celery/.local/bin:${PATH}"

RUN celery --version
