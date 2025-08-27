FROM python:3.11.4-slim

RUN useradd -m uvicorn

USER uvicorn

WORKDIR /usr/src/

COPY ./requirements_dev.txt .

RUN pip install --no-cache-dir -r requirements_dev.txt

COPY ./assets .

COPY ./app .

COPY ./main.py .

COPY ./config.app.json .

ENV PATH="/home/uvicorn/.local/bin:${PATH}"

RUN uvicorn --version