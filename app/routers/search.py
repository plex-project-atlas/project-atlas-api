from   fastapi             import APIRouter, Depends, Path, Query, HTTPException
from   typing              import List, Union
from   libs.models         import SupportedProviders, MediaType, SearchResult
from   starlette.requests  import Request
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


router = APIRouter()


@router.get(
    '/sources/{source}/types/{type}',
    summary        = 'Search for possible matches for the requested media',
    response_model = SearchResult
)
async def search(
    request: Request,
    source:  SupportedProviders = Query(
        ...,
        title       = 'Source',
        description = 'The online source you are targeting'
    ),
    type:    MediaType = Query(
        ...,
        title       = 'Media Type',
        description = 'The type of the media you are searching for'
    ),
    query:   str = Query(
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
    return await request.state.tvdb.search('ita', type, query)