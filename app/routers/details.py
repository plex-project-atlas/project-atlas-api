import logging

from   fastapi             import APIRouter, Path, HTTPException
from   typing              import Dict
from   libs.models         import Movie, Show, SupportedProviders, MediaType
from   starlette.requests  import Request
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


router = APIRouter()


@router.get(
    '/sources/{source}/type/movie/{id}',
    summary        = 'Obtain all the details for the requested movie',
    response_model = Movie
)
async def get_movie_details(
    request: Request,
    source:  SupportedProviders = Path(
        default     = ...,
        title       = 'Source',
        description = 'The online source you are targeting'
    ),
    id:      int = Path(
        default     = ...,
        title       = 'Media ID',
        description = 'The specific ID of the movie within the selected source'
    )
):
    """
    Retrieve details for the requested movie in the selected source.

    The search is performed in italian, with an automatic fallback to the english or native language if no results are found.
    """
    if   source == SupportedProviders.THE_TV_DB:
        return await request.state.tvdb.get_movie(id = id)
    else:
        detail = '[PlexAPI] - Unsupported source selected.'
        logging.error(detail)
        raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = detail)

@router.get(
    '/sources/{source}/type/series/{id}',
    summary        = 'Obtain all the details for the requested show',
    response_model = Show
)
async def get_show_details(
    request: Request,
    source:  SupportedProviders = Path(
        ...,
        title       = 'Source',
        description = 'The online source you are targeting'
    ),
    id:      int = Path(
        ...,
        title        = 'Media ID',
        description  = 'The specific ID of the show within the selected source'
    )
):
    """
    Retrieve details for the requested show in the selected source.

    The search is performed in italian, with an automatic fallback to the english or native language if no results are found.
    """
    if   source == SupportedProviders.THE_TV_DB:
        return await request.state.tvdb.get_show(id = id)
    else:
        detail = '[PlexAPI] - Unsupported source selected.'
        logging.error(detail)
        raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = detail)
