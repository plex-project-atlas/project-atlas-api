from fastapi          import APIRouter, HTTPException
from plexapi.myplex   import MyPlexAccount
from starlette.status import HTTP_200_OK, \
                             HTTP_501_NOT_IMPLEMENTED, \
                             HTTP_511_NETWORK_AUTHENTICATION_REQUIRED
     

from tvdb_api_client import TVDBClient

import os
import logging
import tmdbsimple as tmdb

router = APIRouter()


def env_credentials_check(required_env_vars: list):
    """Verifies that all required environment variables are set.

    Parameters
    ----------
    required_env_vars : list, required
        The list of environment variables to check

    Raises
    ------
    HTTPException
        If any of the required variables is not set or an empty list is passed in
    """

    if not all(env_var in os.environ for env_var in required_env_vars) or not required_env_vars:
        logging.error('Required environment variables not found, raising error...')
        raise HTTPException(status_code = HTTP_511_NETWORK_AUTHENTICATION_REQUIRED, detail = "Network Authentication Required")


@router.get("/", status_code = HTTP_200_OK)
async def match_all(title: str):
    raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = "Not Implemented")


@router.get("/plex", status_code = HTTP_200_OK)
async def match_plex(title: str, media_type: str):
    required_env_vars  = [
        'PLEXAPI_AUTH_MYPLEX_USERNAME',
        'PLEXAPI_AUTH_MYPLEX_PASSWORD'
    ]
    suggested_env_vars = [
        'PLEXAPI_PLEXAPI_ENABLE_FAST_CONNECT',
        'PLEXAPI_PLEXAPI_CONTAINER_SIZE'
    ]
    env_credentials_check(required_env_vars)
    if not all(env_var in os.environ for env_var in suggested_env_vars):
        logging.warning('Suggested environment variables are not set, proceeding anyway...')

    plex_account  = MyPlexAccount()
    project_atlas = plex_account.resource('Project: Atlas').connect()
    plex_results  = project_atlas.search(query = title, mediatype = media_type)

    return [{
        'guid':  elem.guid,
        'title': elem.title,
        'year':  elem.year
    } for elem in plex_results ]


@router.get("/tmdb", status_code = HTTP_200_OK)
async def match_tmdb(title: str, media_type: str):
    required_env_vars  = [
        'TMDB_API_KEY'
    ]
    env_credentials_check(required_env_vars)

    tmdb.API_KEY  = os.environ['TMDB_API_KEY']
    tmdb_search   = tmdb.Search()
    tmdb_response = tmdb_search.movie(query = title) \
                    if media_type == 'movie' else \
                    tmdb_search.tv(query = title)
    tmdb_results  = tmdb_search.results

    return [{
        'guid':  elem['id'],
        'title': elem['title'],
        'year':  elem['release_date'].split('-')[0] if elem['release_date'] else None
    } for elem in tmdb_results]


@router.get("/tvdb", status_code = HTTP_200_OK)
async def match_tvdb(title: str, media_type: str):
    required_env_vars  = [
        'TVDB_USR_NAME',
        'TVDB_USR_KEY',
        'TVDB_API_KEY'
    ]
    env_credentials_check(required_env_vars)

    tvdb         = TVDBClient(os.environ['TVDB_USR_NAME'], os.environ['TVDB_USR_KEY'], os.environ['TVDB_API_KEY'])
    tvdb_results = tvdb.find_series_by_name(title)

    return [{
        'guid':  elem['tvdb_id'],
        'title': elem['name'],
        'year':  elem['air_date'].split('-')[0] if elem['air_date'] else None
    } for elem in tvdb_results ]
