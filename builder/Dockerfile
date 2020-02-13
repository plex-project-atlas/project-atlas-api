FROM python:3.8.1-slim-buster

RUN mkdir /plex-api

COPY . /plex-api

RUN  apt-get update && apt-get install -y gcc && \
     yes | pip install --no-cache-dir -r /plex-api/builder/requirements.txt && \
     rm -fr /var/lib/apt/lists/*

WORKDIR /plex-api

ENV PLEXAPI_AUTH_SERVER_BASEURL http://nas.okloud.it:32400
ENV PLEXAPI_PLEXAPI_ENABLE_FAST_CONNECT true
ENV PLEXAPI_AUTH_SRV_NAME Project: Atlas
ENV PLEXAPI_PLEXAPI_CONTAINER_SIZE 1000
ENV IMDB_DB_PROJECT plex-project-atlas
ENV IMDB_DB_REGION europe-west3

CMD ["python3", "/plex-api/main.py"]

EXPOSE 8080/tcp