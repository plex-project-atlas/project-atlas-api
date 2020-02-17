FROM python:3.8.1-slim

COPY . /plex-api

WORKDIR /plex-api

RUN  apt-get update && apt-get install -y gcc && \
     yes | pip install --no-cache-dir -r builder/requirements.txt && \
     rm -fr /var/lib/apt/lists/*

ENV PLEXAPI_AUTH_SERVER_BASEURL=http://nas.okloud.it:32400 \
    PLEXAPI_PLEXAPI_ENABLE_FAST_CONNECT=true \
    PLEXAPI_AUTH_SRV_NAME="Project: Atlas" \
    PLEXAPI_PLEXAPI_CONTAINER_SIZE=1000 \
    DB_PROJECT=plex-project-atlas \
    DB_REGION=europe-west3

CMD ["python3", "main.py"]

EXPOSE 8080/tcp