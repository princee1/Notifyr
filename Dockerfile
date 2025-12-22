FROM python:3.11.4-slim as builder

COPY ./requirements.txt .

RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt --prefix=/install

FROM python:3.11.4-slim

RUN useradd -m notifyr

USER notifyr

WORKDIR /usr/src/

COPY --from=builder /install /usr/local/

ENV PATH="/home/notifyr/.local/bin:${PATH}"

RUN uvicorn --version

COPY ./gunicorn_main.py .

COPY ./main.py .

COPY ./app/ ./app/