FROM python:3.11

RUN apt-get update && apt-get install -y make

RUN useradd -m celery

USER celery

WORKDIR /usr/src/

COPY ./app ./app/

COPY ./requirements_dev.txt .

COPY ./Makefile .

RUN make install

RUN pip show celery

ENV PATH="/celery/.local/bin:${PATH}"

# Verify that celery is available in the PATH
RUN celery --version
