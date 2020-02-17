import os
import logging

from   fastapi          import HTTPException
from   typing           import List
from   pydantic         import BaseModel, AnyHttpUrl
from   starlette.status import HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


def env_vars_check(required_env_vars, suggested_env_vars: list):
    if not all(env_var in os.environ for env_var in required_env_vars) or not required_env_vars:
        logging.error('Required environment variables not found, raising error...')
        raise HTTPException(status_code = HTTP_511_NETWORK_AUTHENTICATION_REQUIRED, detail = "Network Authentication Required")
    if not all(env_var in os.environ for env_var in suggested_env_vars):
        logging.warning('Suggested environment variables are not set, proceeding anyway...')


class EpisodeObject(BaseModel):
    title: str
    lang:  str


class SeasonObject(BaseModel):
    episodes: List[EpisodeObject]


class ResultObject(BaseModel):
    guid:    str
    title:   str
    type:    str
    year:    int                = None
    poster:  AnyHttpUrl         = None
    seasons: List[SeasonObject] = None


class ResultAllObject(BaseModel):
    imdb: List[ResultObject]
    tmdb: List[ResultObject]
    tvdb: List[ResultObject]


class MatchResults(BaseModel):
    query:   str
    results: List[ResultObject] = []


class MatchAllResult(BaseModel):
    query:   str
    results: ResultAllObject
