FROM python:3.11-slim

RUN apt-get update && apt-get install -y make

RUN useradd -m celery

USER celery

WORKDIR /usr/src/

COPY ./app ./app/

COPY ./requirements_dev.txt .

COPY ./Makefile .

RUN make install

RUN pip show celery

ENV PATH="/home/celery/.local/bin:${PATH}"

RUN celery --version
