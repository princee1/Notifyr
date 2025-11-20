FROM python:3.11.4-slim

RUN useradd -m notifyr

USER notifyr

WORKDIR /usr/src/

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./gunicorn_main.py .

COPY ./main.py .

COPY ./app/ ./app/

ENV PATH="/home/notifyr/.local/bin:${PATH}"

RUN uvicorn --version