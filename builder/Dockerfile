FROM python:3.8.1-slim-buster

RUN mkdir /plex-api

COPY . /plex-api

RUN  apt-get update && apt-get install -y gcc && \
     yes | pip install --no-cache-dir -r /plex-api/builder/requirements.txt && \
     rm -fr /var/lib/apt/lists/*

WORKDIR /plex-api

CMD ["python3", "/plex-api/main.py"]

EXPOSE 8080/tcp