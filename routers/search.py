import asyncio

from   fastapi             import APIRouter, Depends, Path, Query, HTTPException
from   typing              import List
from   libs.models         import verify_plex_env_variables, verify_tmdb_env_variables, verify_tvdb_env_variables, \
                                  MatchAll, Media
from   starlette.requests  import Request
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


router = APIRouter()


@router.get(
    '',
    summary        = 'Search across all supported APIs',
    dependencies   = [
        Depends(verify_plex_env_variables),
        Depends(verify_tmdb_env_variables),
        Depends(verify_tvdb_env_variables)
    ],
    response_model = MatchAll,
    responses      = {
        HTTP_501_NOT_IMPLEMENTED: {}
    }
)
async def search_all(
        request:     Request,
        media_title: str = Query(
            ...,
            title        = 'Search Query',
            description  = 'The title of media you are searching for',
            min_length   = 3
        )
):
    """
    Search the requested string across all defined endpoints.

    Performs a full, asynchronous research across all supported APIs, merges the duplicated results and returns an
    ordered list

    **Parameters constraints:**
    - ***media_title:*** must be at least 3 characters long

    **Notes:**
    - The returned object will contain _service.results.seasons_ only if _media_type_ is _show_
    """
    requests  = [
        request.state.imdb.search_media_by_name([media_title], None),
        request.state.tmdb.search_media_by_name([{'title': media_title, 'type': 'movie'}]),
        request.state.tmdb.search_media_by_name([{'title': media_title, 'type': 'show'}]),
        request.state.tvdb.search_media_by_name([{'title': media_title, 'type': 'show'}]),
    ]
    responses = await asyncio.gather(*requests)

    results = {
        'query':   media_title,
        'results': {
            'imdb': responses[0][0]['results'],
            'tmdb': responses[1][0]['results'] + responses[2][0]['results'],
            'tvdb': responses[3][0]['results']
        }
    }

    return results


@router.get(
    '/plex/{media_type}',
    summary        = 'Search into Project: Atlas Database',
    dependencies   = [Depends(verify_plex_env_variables)],
    response_model = List[Media],
    responses      = {
        HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
    }
)
async def match_plex(
        request: Request,
        media_type: str   = Path(
            ...,
            title         = 'Search Type',
            description   = 'The type of media you are searching for',
            regex         = '^(movie|show)$'
        ),
        media_titles: str = Query(
            ...,
            title         = 'Search Query',
            description   = 'The title(s) of media you are searching for',
            min_length    = 3
        )
):
    """
    Search for the requested string in the Project: Atlas database.

    Extracts the results from all the items in your Plex library.
    This searches for both movies and TV shows.
    It performs spell-checking against your search terms (because KUROSAWA is hard to spell).
    It also provides contextual search results.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***media_titles:*** must be at least 3 characters long

    **Notes:**
    - The input string will be *splitted by commas* performing multiple, parallel requests.
    - The returned object will contain _[*].results.seasons_ only if _media_type_ is _show_
    """

    plex_results = request.state.plex.search_media_by_name(media_titles.split(','), media_type, request.state.cache)
    if not plex_results:
        raise HTTPException(status_code = HTTP_503_SERVICE_UNAVAILABLE, detail = 'Service Unavailable')

    return plex_results


@router.get(
    '/imdb/{media_type}',
    summary        = 'Search into IMDb Database',
    response_model = List[Media]
)
async def match_imdb(
    request: Request,
    media_type: str   = Path(
        ...,
        title         = 'Search Type',
        description   = 'The type of media you are searching for',
        regex         = '^(movie|show)$'
    ),
    media_title: str  = Query(
        ...,
        title         = 'Search Query',
        description   = 'The title of media you are searching for',
        min_length    = 3
    )
):
    """
    Search for the requested string in the IMDb database.

    Currently supports searching for movies and TV shows in IMDb database.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***media_title:*** must be at least 3 characters long
    """
    return await request.state.imdb.search_media_by_name(request, media_title.strip(), media_type)


@router.get(
    '/tmdb/{media_type}',
    summary        = 'Search into TMDb Database',
    dependencies   = [Depends(verify_tmdb_env_variables)],
    response_model = List[Media],
    responses      = {
        HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
    }
)
async def search_tmdb(
        request: Request,
        media_type: str   = Path(
            ...,
            title         = 'Search Type',
            description   = 'The type of media you are searching for',
            regex         = '^(movie|show)$'
        ),
        media_title: str  = Query(
            ...,
            title         = 'Search Query',
            description   = 'The title of media you are searching for',
            min_length    = 3
        )
):
    """
    Search for the requested string in The Movie DB database.

    Currently supports searching for movies and TV shows in The Movie DB database.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***media_title:*** must be at least 3 characters long
    """
    return await request.state.tmdb.search_media_by_name(media_title.strip(), media_type, request.state.cache)


@router.get(
    '/tvdb/{media_type}',
    summary        = 'Search into TheTVDB Database',
    dependencies   = [Depends(verify_tvdb_env_variables)],
    response_model = List[Media],
    responses      = {
        HTTP_511_NETWORK_AUTHENTICATION_REQUIRED: {}
    }
)
async def search_tvdb(
        request: Request,
        media_type: str   = Path(
            ...,
            title         = 'Search Type',
            description   = 'The type of media you are searching for',
            regex         = '^(movie|show)$'
        ),
        media_title: str  = Query(
            ...,
            title         = 'Search Query',
            description   = 'The title of media you are searching for',
            min_length    = 3
        )
):
    """
    Search for the requested string in TheTVDB database.

    Currently supports searching for TV shows in TheTVDB database.

    **Parameters constraints:**
    - ***media_type:*** must be one of: *movie*, *show*
    - ***media_title:*** must be at least 3 characters long
    """
    return await request.state.tvdb.search_media_by_name(media_title.strip(), media_type, request.state.cache)
