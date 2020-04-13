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


def verify_plex_env_variables():
    required  = [
        'PLEXAPI_AUTH_MYPLEX_USERNAME',
        'PLEXAPI_AUTH_MYPLEX_PASSWORD',
        'PLEXAPI_AUTH_SERVER_BASEURL',
        'PLEXAPI_AUTH_SRV_NAME'
    ]
    suggested = [
        'PLEXAPI_PLEXAPI_ENABLE_FAST_CONNECT',
        'PLEXAPI_PLEXAPI_CONTAINER_SIZE'
    ]
    env_vars_check(required, suggested)


def verify_tmdb_env_variables():
    required  = [
        'TMDB_API_TOKEN'
    ]
    suggested = []
    env_vars_check(required, suggested)


def verify_tvdb_env_variables():
    required  = [
        'TVDB_USR_NAME',
        'TVDB_USR_KEY',
        'TVDB_API_KEY'
    ]
    suggested = []
    env_vars_check(required, suggested)


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


class TMDbMatchRequest(BaseModel):
    id:             str
    type:           str
    external:       str = None


class RequestDetails(BaseModel):
    request_date:    str
    user_id:         int
    user_name:       str
    user_first_name: str = None
    user_last_name:  str = None
    request_notes:   str = None


class RequestObject(BaseModel):
    request_id:      str
    request_type:    str
    request_season:  int = None
    request_status:  str
    plex_notes:      str = None
    request_count:   int
    request_info:    ResultObject
    request_list:    List[RequestDetails]
