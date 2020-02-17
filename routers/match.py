import asyncio

from   fastapi             import APIRouter, Depends, Path, Query, HTTPException
from   typing              import List
from   libs.models         import env_vars_check, MatchAllResult, MatchResults
from   starlette.requests  import Request
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


router = APIRouter()


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


@router.get(
    '',
    summary        = 'Match all supported APIs',
    dependencies   = [
        Depends(verify_plex_env_variables),
        Depends(verify_tmdb_env_variables),
        Depends(verify_tvdb_env_variables)
    ],
    response_model = MatchAllResult,
    responses      = {
        HTTP_501_NOT_IMPLEMENTED: {}
    }
)
async def match_all(
        request: Request,
        title: str = Query(..., min_length = 3)
):
    """
    Match the requested string against all defined endpoints.

    Performs a full, asynchronous research across all supported APIs, merges the duplicated results and returns an
    ordered list

    **Parameters constraints:**
    - ***title:*** must be at least 3 characters long

    **Notes:**
    - The returned object will contain _service.results.seasons_ only if _media_type_ is _show_
    """
    requests  = [
        request.state.imdb.search_media_by_name([title], None),
        request.state.tmdb.search_movie_by_name([title]),
        request.state.tmdb.search_show_by_name([title]),
        request.state.tvdb.search_show_by_name([title])
    ]
    responses = await asyncio.gather(*requests)

    results = {
        'query':   title,
        'results': {
            'imdb': responses[0][0]['results'],
            'tmdb': responses[1][0]['results'] + responses[2][0]['results'],
            'tvdb': responses[3][0]['results']
        }
    }

    return results


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
        request: Request,
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

    plex_results = request.state.plex.search_media_by_name(titles.split(','), media_type)
    if not plex_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return plex_results


@router.get(
    '/imdb/{media_type}',
    summary        = 'Match IMDb Database',
    response_model = List[MatchResults]
)
async def match_imdb(
        request: Request,
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
    imdb_results = await request.state.imdb.search_media_by_name(titles.split(','), media_type)
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
        request: Request,
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
        tmdb_results = await request.state.tmdb.search_movie_by_name( titles.split(',') )
    else:
        tmdb_results = await request.state.tmdb.search_show_by_name( titles.split(',') )
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
        request: Request,
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
    tvdb_results = await request.state.tvdb.search_show_by_name( titles.split(',') )
    if not tvdb_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return tvdb_results
