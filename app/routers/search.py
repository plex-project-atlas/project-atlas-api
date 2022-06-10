import logging

from   fastapi             import APIRouter, Path, Query, HTTPException
from   typing              import Any, List, Dict
from   libs.models         import SupportedProviders, MediaType, SearchResult, Show
from   starlette.requests  import Request
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED


router = APIRouter()


@router.get(
    '/sources/{source}',
    summary        = 'Search for possible matches for the requested media',
    response_model = SearchResult
)
async def search(
    request: Request,
    source:  SupportedProviders = Path(
        default     = ...,
        title       = 'Source',
        description = 'The online source you are targeting'
    ),
    query:   str = Query(
        default     = ...,
        title       = 'Search Query',
        description = 'The title of media you are searching for',
        min_length  = 3
    ),
    type:    MediaType = Query(
        default     = None,
        title       = 'Media Type',
        description = 'The type of the media you are searching for'
    )
):
    """
    Search for the requested media in the selected source.

    The search is performed in italian, with an automatic fallback to the english or native language if no results are found.
    """
    if   source == SupportedProviders.THE_TV_DB:
        return await request.state.tvdb.do_search(query = query, type = type)
    elif source == SupportedProviders.THE_MOVIE_DB:
        return await request.state.tmdb.do_search(query = query, type = type)

    detail = '[PlexAPI] - Function not yet implemented.'
    logging.error(detail)
    return HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = detail)