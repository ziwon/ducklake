FROM apache/airflow:2.9.1-python3.11

ARG DOCKER_GROUP_ID

USER root
RUN groupadd -g ${DOCKER_GROUP_ID} docker && \
    usermod -aG docker airflow
USER airflow