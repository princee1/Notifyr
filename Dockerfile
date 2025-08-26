FROM python:3.11-slim AS builder

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

RUN useradd -m server

USER server

WORKDIR /usr/src/

COPY --from=builder /usr/local/lib/python*/site-packages /usr/local/lib/python*/site-packages

COPY ./assets .

COPY ./app .

COPY ./main.py .

COPY ./config.app.json .