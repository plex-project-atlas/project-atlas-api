import os
import logging

from   fastapi             import APIRouter, HTTPException
from   typing              import List
from   pydantic            import BaseModel, AnyHttpUrl
from   plexapi.myplex      import MyPlexAccount, PlexServer
from   libs.tmdb           import TMDBClient
from   libs.tvdb           import TVDBClient
from   libs.imdb           import IMDBClient
from   starlette.status    import HTTP_404_NOT_FOUND, \
                                  HTTP_415_UNSUPPORTED_MEDIA_TYPE, \
                                  HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


class MatchMovieResult(BaseModel):
    title:  str
    guid:   str
    year:   int
    poster: AnyHttpUrl


class MatchMovieResponse(BaseModel):
    query:   str
    results: List[MatchMovieResult] = []


router = APIRouter()
tmdb   = TMDBClient()
tvdb   = TVDBClient()
imdb   = IMDBClient()
plex   = MyPlexAccount().resource('Project: Atlas')
plex   = PlexServer(token = plex.accessToken)


def env_credentials_check(required_env_vars: list):
    if not all(env_var in os.environ for env_var in required_env_vars) or not required_env_vars:
        logging.error('Required environment variables not found, raising error...')
        raise HTTPException(status_code = HTTP_511_NETWORK_AUTHENTICATION_REQUIRED, detail = "Network Authentication Required")


def verify_media_type(media_type: str):
    if media_type not in ['movie', 'show']:
        raise HTTPException(status_code = HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail = "Unsupported Media Type")


@router.get('/', summary = 'Match all supported APIs',
            responses = { HTTP_501_NOT_IMPLEMENTED: {} })
async def match_all(titles: str):
    """
    Match the requested string against all defined endpoints.

    Performs a full, asynchronous research across all supported APIs, merges the duplicated results and returns an
    ordered list
    """
    raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = "Not Implemented")


@router.get('/imdb/{media_type}', summary = 'Match IMDb Database')
async def match_imdb(titles, media_type: str):
    """
    Match the requested string against IMDb database.

    Currently supports searching for movies and TV shows in IMDb database.

    **Note:** The input string will be *splitted by commas and trimmed* performing multiple, parallel requests.
    """
    imdb_results = await imdb.search_show_by_name(titles.split(','), media_type)
    if not imdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return imdb_results


@router.get('/plex/{media_type}', summary = 'Match Project: Atlas Database',
            responses = { HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {} })
async def match_plex(titles, media_type: str):
    """
    Match the requested string against Project: Atlas database.

    Extracts the results from Hub Search against all items in your Plex library.
    This searches for movies and TV shows.
    It performs spell-checking against your search terms (because KUROSAWA is hard to spell).
    It also provides contextual search results.

    **Note:** The input string will be *splitted by commas and trimmed* performing multiple, parallel requests.
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

    results = []
    for title in titles.split(','):
        try:
            plex_results = plex.search(query = title.strip(), mediatype = media_type)
            results.append({
                'query':   title.strip(),
                'results': [{
                    'guid':  elem.guid,
                    'title': elem.title,
                    'type':  elem.type,
                    'year':  elem.year
                } for elem in plex_results if elem.type == media_type]
            })
        except:
            raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return results


@router.get('/tmdb/{media_type}', summary = 'Match TMDb Database',
            responses = { HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {} })
async def match_tmdb(titles, media_type: str):
    """
    Match the requested string against The Movie DB database.

    Search multiple models in a single request.
    Currently supports searching for movies and TV shows in The Movie DB database.

    **Note:** The input string will be *splitted by commas* performing multiple, parallel requests.
    """
    required_env_vars  = [
        'TMDB_API_TOKEN'
    ]
    env_credentials_check(required_env_vars)
    verify_media_type(media_type)

    if media_type == 'movie':
        tmdb_results = await tmdb.search_movie_by_name( titles.split(',') )
    else:
        tmdb_results = await tmdb.search_show_by_name( titles.split(',') )
    if not tmdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return tmdb_results


@router.get('/tvdb/{media_type}', summary = 'Match TheTVDB Database',
            responses = { HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {} })
async def match_tvdb(titles, media_type: str):
    """
    Match the requested string against TheTVDB database.

    Currently supports searching for TV shows in TheTVDB database.

    **Note:** The input string will be *splitted by commas* performing multiple, parallel requests.
    """
    if media_type != 'show':
        raise HTTPException(status_code = HTTP_404_NOT_FOUND, detail = 'Not Found')

    required_env_vars  = [
        'TVDB_USR_NAME',
        'TVDB_USR_KEY',
        'TVDB_API_KEY'
    ]
    env_credentials_check(required_env_vars)

    tvdb_results = await tvdb.search_show_by_name( titles.split(',') )
    if not tvdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return tvdb_results

