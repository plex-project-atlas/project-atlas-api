from   fastapi             import APIRouter, Path, Query
from   typing              import Any, List, Dict
from   libs.models         import SupportedProviders, MediaType, SearchResult, Show
from   starlette.requests  import Request
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


router = APIRouter()


@router.get(
    '/sources/{source}/types/{type}',
    summary        = 'Search for possible matches for the requested media',
    response_model = Any
)
async def search(
    request: Request,
    source:  SupportedProviders = Path(
        ...,
        title       = 'Source',
        description = 'The online source you are targeting'
    ),
    type:    MediaType = Path(
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
    Search for the requested media in the selected source.

    The search is performed in italian, with an automatic fallback to the english language if no results are found.
    """
    return True # Needs a rework to accomodate new models
    #return await request.state.tvdb.do_search('ita', type, query)