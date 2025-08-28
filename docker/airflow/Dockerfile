FROM apache/airflow:2.9.3

USER root
RUN apt-get update -y && apt-get install -y --no-install-recommends docker.io curl \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir \
    pymysql \
    openlineage-airflow==1.36.0
