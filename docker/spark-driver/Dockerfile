FROM bitnami/spark:3.5.5

ARG spark_uid

USER root

COPY ./src/jobs/spark/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./src/jobs/spark/quotes_ingest.py /app/quotes_ingest.py

WORKDIR /app

USER ${spark_uid}
