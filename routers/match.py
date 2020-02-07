import os
import asyncio
import logging

from   fastapi             import APIRouter, Depends, Path, Query, HTTPException
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


router = APIRouter()
tmdb   = TMDBClient()
tvdb   = TVDBClient()
imdb   = IMDBClient()
try:
    plex = MyPlexAccount().resource('Project: Atlas')
    plex = PlexServer(token = plex.accessToken)
except:
    plex = None


class EpisodeObject(BaseModel):
    title: str
    lang:  str


class SeasonObject(BaseModel):
    episodes: List[EpisodeObject]


class ResultObject(BaseModel):
    guid:    str
    title:   str
    type:    str
    year:    int
    poster:  AnyHttpUrl = None
    seasons: List[SeasonObject] = None


class MatchResults(BaseModel):
    query:   str
    results: List[ResultObject] = []


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
        'PLEXAPI_AUTH_SERVER_BASEURL'
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


@router.get(
    '/',
    summary        = 'Match all supported APIs',
    dependencies   = [
        Depends(verify_plex_env_variables),
        Depends(verify_tmdb_env_variables),
        Depends(verify_tvdb_env_variables)
    ],
    #response_model = List[MatchResults],
    responses      = {
        HTTP_501_NOT_IMPLEMENTED: {}
    }
)
async def match_all(
        title: str = Query(..., min_length = 3)
):
    """
    Match the requested string against all defined endpoints.

    Performs a full, asynchronous research across all supported APIs, merges the duplicated results and returns an
    ordered list

    **Parameters constraints:**
    - ***title:*** must be at least 3 characters long

    **Notes:**
    - The returned object will contain _[*].results.seasons_ only if _media_type_ is _show_
    """
    requests  = [
        imdb.search_media_by_name([title], 'movie'),
        imdb.search_media_by_name([title], 'show'),
        tmdb.search_movie_by_name([title]),
        tmdb.search_show_by_name([title]),
        tvdb.search_show_by_name([title])
    ]
    responses = await asyncio.gather(*requests)

    responses = [result for databases in responses for database in databases for result in database['results']]

    return responses


@router.get(
    '/plex/{media_type}',
    summary        = 'Match Project: Atlas Database',
    dependencies   = [Depends(verify_plex_env_variables)],
    response_model = List[MatchResults],
    responses      = {
        HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
    }
)
async def match_plex(
        media_type: str = Path(
            ...,
            title       = 'Search Type',
            description = 'The type of media you are searching for',
            regex       = '^(movie|show)$'
        ),
        titles: str     = Query(
            ...,
            title       = 'Search Query',
            description = 'The title(s) of media you are searching for',
            min_length  = 3
        )
):
    """
    Match the requested string against Project: Atlas database.

    Extracts the results from Hub Search against all items in your Plex library.
    This searches for movies and TV shows.
    It performs spell-checking against your search terms (because KUROSAWA is hard to spell).
    It also provides contextual search results.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***titles:*** must be at least 3 characters long

    **Notes:**
    - The input string will be *splitted by commas* performing multiple, parallel requests.
    - The returned object will contain _[*].results.seasons_ only if _media_type_ is _show_
    """
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


@router.get(
    '/imdb/{media_type}',
    summary        = 'Match IMDb Database',
    response_model = List[MatchResults]
)
async def match_imdb(
        media_type: str = Path(
            ...,
            title       = 'Search Type',
            description = 'The type of media you are searching for',
            regex       = '^(movie|show)$'
        ),
        titles: str     = Query(
            ...,
            title       = 'Search Query',
            description = 'The title(s) of media you are searching for',
            min_length  = 3
        )
):
    """
    Match the requested string against IMDb database.

    Currently supports searching for movies and TV shows in IMDb database.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***titles:*** must be at least 3 characters long

    **Notes:**
    - The input string will be *splitted by commas* performing multiple, parallel requests.
    - The returned object will contain _[*].results.seasons_ only if _media_type_ is _show_
    """
    imdb_results = await imdb.search_media_by_name(titles.split(','), media_type)
    if not imdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return imdb_results


@router.get(
    '/tmdb/{media_type}',
    summary        = 'Match TMDb Database',
    dependencies   = [Depends(verify_tmdb_env_variables)],
    response_model = List[MatchResults],
    responses      = {
        HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
    }
)
async def match_tmdb(
        media_type: str = Path(
            ...,
            title       = 'Search Type',
            description = 'The type of media you are searching for',
            regex       = '^(movie|show)$'
        ),
        titles: str     = Query(
            ...,
            title       = 'Search Query',
            description = 'The title(s) of media you are searching for',
            min_length  = 3
        )
):
    """
    Match the requested string against The Movie DB database.

    Search multiple models in a single request.
    Currently supports searching for movies and TV shows in The Movie DB database.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***titles:*** must be at least 3 characters long

    **Notes:**
    - The input string will be *splitted by commas* performing multiple, parallel requests.
    - The returned object will contain _[*].results.seasons_ only if _media_type_ is _show_
    """
    if media_type == 'movie':
        tmdb_results = await tmdb.search_movie_by_name( titles.split(',') )
    else:
        tmdb_results = await tmdb.search_show_by_name( titles.split(',') )
    if not tmdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return tmdb_results


@router.get(
    '/tvdb/{media_type}',
    summary        = 'Match TheTVDB Database',
    dependencies   = [Depends(verify_tvdb_env_variables)],
    response_model = List[MatchResults],
    responses      = {
        HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
    }
)
async def match_tvdb(
        media_type: str = Path(
            ...,
            title       = 'Search Type',
            description = 'The type of media you are searching for',
            regex       = '^(movie|show)$'
        ),
        titles: str     = Query(
            ...,
            title       = 'Search Query',
            description = 'The title(s) of media you are searching for',
            min_length  = 3
        )
):
    """
    Match the requested string against TheTVDB database.

    Currently supports searching for TV shows in TheTVDB database.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***titles:*** must be at least 3 characters long

    **Notes:**
    - The input string will be *splitted by commas* performing multiple, parallel requests.
    - The returned object will contain _[*].results.seasons_ only if _media_type_ is _show_
    """
    tvdb_results = await tvdb.search_show_by_name( titles.split(',') )
    if not tvdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return tvdb_results

