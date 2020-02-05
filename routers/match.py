import os
import logging

from   fastapi             import APIRouter, HTTPException
from   typing              import List
from   pydantic            import BaseModel, Field
from   plexapi.myplex      import MyPlexAccount, PlexServer
from   libs.tmdb           import TMDBClient
from   libs.tvdb           import TVDBClient
from   libs.imdb           import IMDBClient
from   starlette.responses import JSONResponse
from   starlette.status    import HTTP_200_OK, \
                                  HTTP_404_NOT_FOUND, \
                                  HTTP_415_UNSUPPORTED_MEDIA_TYPE, \
                                  HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED

router = APIRouter()
tmdb   = TMDBClient()
tvdb   = TVDBClient()
imdb   = IMDBClient()
plex   = MyPlexAccount().resource('Project: Atlas')
plex   = PlexServer(token = plex.accessToken)


class MatchResult(BaseModel):
    title: 'str' = Field(None, title="The description of the item", max_length=300)
    guid: str
    type: str
    year: str


class MatchResultList(BaseModel):
    query: str
    results: List[MatchResult] = []


def env_credentials_check(required_env_vars: list):
    if not all(env_var in os.environ for env_var in required_env_vars) or not required_env_vars:
        logging.error('Required environment variables not found, raising error...')
        raise HTTPException(status_code = HTTP_511_NETWORK_AUTHENTICATION_REQUIRED, detail = "Network Authentication Required")


def verify_media_type(media_type: str):
    if media_type not in ['movie', 'show']:
        raise HTTPException(status_code = HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail = "Unsupported Media Type")


@router.get('/', summary = 'Match all supported APIs',
            responses = {
                HTTP_200_OK:                              {},
                HTTP_404_NOT_FOUND:                       {},
                HTTP_503_SERVICE_UNAVAILABLE:             {},
                HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
            })
async def match_all(title: str):
    """
    Match the requested string against all defined endpoints.

    Performs a full, asynchronous research across all supported APIs, merges the duplicated results and returns an
    ordered list
    """
    raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = "Not Implemented")


@router.get('/plex/{media_type}', summary = 'Match Project: Atlas Database',
            responses = {
                HTTP_200_OK:                              {},
                HTTP_404_NOT_FOUND:                       {},
                HTTP_503_SERVICE_UNAVAILABLE:             {},
                HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
            })
async def match_plex(title: str, media_type: str):
    """
    Match the requested string against Project: Atlas database.

    Extracts the results from Hub Search against all items in your Plex library.
    This searches for movies and TV shows.
    It performs spell-checking against your search terms (because KUROSAWA is hard to spell).
    It also provides contextual search results.
    """
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


@router.get('/tmdb/{media_type}', summary = 'Match TMDb Database',
            responses = {
                HTTP_200_OK:                              {},
                HTTP_404_NOT_FOUND:                       {},
                HTTP_503_SERVICE_UNAVAILABLE:             {},
                HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
            })
async def match_tmdb(title: str, media_type: str):
    """
    Match the requested string against The Movie DB database.

    Search multiple models in a single request.
    Currently supports searching for movies and TV shows in The Movie DB database.
    """
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


@router.get('/tvdb', summary = 'Match TheTVDB Database',
            responses = {
                HTTP_200_OK:                  {},
                HTTP_404_NOT_FOUND:           {},
                HTTP_503_SERVICE_UNAVAILABLE: {}
            })
async def match_tvdb(title: str):
    """
    Match the requested string against TheTVDB database.

    Currently supports searching for TV shows in TheTVDB database.
    """
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


@router.get('/imdb', summary = 'Match IMDb Database',
            responses = {
                HTTP_200_OK:                  {},
                HTTP_404_NOT_FOUND:           {},
                HTTP_503_SERVICE_UNAVAILABLE: {}
            })
async def match_imdb(title: str):
    """
    Match the requested string against IMDb database.

    Currently supports searching for movies and TV shows in IMDb database.
    """
    imdb_query = await imdb.search_show_by_name(title)
    if not imdb_query:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    if imdb_query['results']:
        return imdb_query
    else:
        return JSONResponse(status_code = HTTP_404_NOT_FOUND, content = imdb_query)
