import os
import logging

from   fastapi          import APIRouter, HTTPException
from   plexapi.myplex   import MyPlexAccount
from   typing           import Union, List
from   libs.tmdb        import TMDBClient
from   libs.tvdb        import TVDBClient
from   starlette.status import HTTP_200_OK, \
                               HTTP_415_UNSUPPORTED_MEDIA_TYPE, \
                               HTTP_501_NOT_IMPLEMENTED, \
                               HTTP_503_SERVICE_UNAVAILABLE, \
                               HTTP_511_NETWORK_AUTHENTICATION_REQUIRED

router = APIRouter()
tmdb   = TMDBClient()
tvdb   = TVDBClient()
plex   = MyPlexAccount().resource('Project: Atlas').connect()


def env_credentials_check(required_env_vars: list):
    if not all(env_var in os.environ for env_var in required_env_vars) or not required_env_vars:
        logging.error('Required environment variables not found, raising error...')
        raise HTTPException(status_code = HTTP_511_NETWORK_AUTHENTICATION_REQUIRED, detail = "Network Authentication Required")


def verify_media_type(media_type: str):
    if media_type not in ['movie', 'show']:
        raise HTTPException(status_code = HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail = "Unsupported Media Type")


@router.get("/", status_code = HTTP_200_OK)
async def match_all(title: str):
    raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = "Not Implemented")


@router.get("/plex/{media_type}", status_code = HTTP_200_OK)
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
    verify_media_type(media_type)
    if not all(env_var in os.environ for env_var in suggested_env_vars):
        logging.warning('Suggested environment variables are not set, proceeding anyway...')

    plex_results  = plex.search(query = title, mediatype = media_type)

    return [{
        'guid':  elem.guid,
        'title': elem.title,
        'year':  elem.year
    } for elem in plex_results ]


@router.get("/tmdb/{media_type}", status_code = HTTP_200_OK)
async def match_tmdb(title: str, media_type: str):
    required_env_vars  = [
        'TMDB_API_KEY'
    ]
    env_credentials_check(required_env_vars)
    verify_media_type(media_type)

    if media_type == 'movie':
        tmdb_results = tmdb.search_movie_by_name(title)
    else:
        tmdb_results = tmdb.search_show_by_name(title)

    if not tmdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return tmdb_results


@router.get("/tvdb", status_code = HTTP_200_OK)
async def match_tvdb(title: str):
    required_env_vars  = [
        'TVDB_USR_NAME',
        'TVDB_USR_KEY',
        'TVDB_API_KEY'
    ]
    env_credentials_check(required_env_vars)

    tvdb_results = await tvdb.search_show_by_name(title)
    if not tvdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return tvdb_results
