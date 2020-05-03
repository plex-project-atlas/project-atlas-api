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
    """
    requests  = [
        request.state.imdb.search_media_by_name(request, media_title, 'movie'),
        request.state.imdb.search_media_by_name(request, media_title, 'show'),
        request.state.tmdb.search_media_by_name(media_title, 'movie', request.state.cache),
        request.state.tmdb.search_media_by_name(media_title, 'show',  request.state.cache),
        request.state.tvdb.search_media_by_name(media_title, 'show',  request.state.cache),
    ]
    responses = await asyncio.gather(*requests)

    media_search = {
        'imdb': responses[0] + responses[1],
        'tmdb': responses[2] + responses[3],
        'tvdb': responses[4]
    }
    return media_search


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
        media_type: str  = Path(
            ...,
            title        = 'Search Type',
            description  = 'The type of media you are searching for',
            regex        = '^(movie|show)$'
        ),
        media_title: str = Query(
            ...,
            title        = 'Search Query',
            description  = 'The title of media you are searching for',
            min_length   = 3
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
    - ***media_title:*** must be at least 3 characters long
    """
    return request.state.plex.search_media_by_name(media_title, media_type, request.state.cache)


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
