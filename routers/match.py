import asyncio

from   fastapi             import APIRouter, Depends, Path, HTTPException
from   libs.models         import verify_plex_env_variables, verify_tmdb_env_variables, verify_tvdb_env_variables, \
                                  Media
from   starlette.requests  import Request
from   starlette.status    import HTTP_404_NOT_FOUND, HTTP_501_NOT_IMPLEMENTED


router = APIRouter()


@router.get(
    '/{media_type}/{media_db}/{media_id}',
    summary        = 'Match across all supported APIs',
    dependencies   = [
        Depends(verify_plex_env_variables),
        Depends(verify_tmdb_env_variables),
        Depends(verify_tvdb_env_variables)
    ],
    response_model = Media
)
async def match_id(
    request:    Request,
    media_type: str = Path(
        ...,
        title       = 'Search Type',
        description = 'The type of media you are searching for',
        regex       = '^(movie|show)$'
    ),
    media_db: str   = Path(
        ...,
        title       = 'Search Type',
        description = 'The type of media you are searching for',
        regex       = '^(plex|imdb|tmdb|tvdb)$'
    ),
    media_id: str   = Path(
        ...,
        title       = 'Search Type',
        description = 'The type of media you are searching for',
        regex       = '^\w+$'
    )
):
    """
    Match the requested ID against all known databases.

    Performs a full, asynchronous research across all supported APIs and returns an ordered list

    **Parameters constraints:**
    - ***media_id:*** must be a Plex, IMDb, TMDb or TVDb ID

    **Notes:**
    - The returned object will contain _service.results.seasons_ only if _media_type_ is _show_
    """
    if media_db == 'imdb':
        media_info = await request.state.tmdb.get_media_by_id([media_db + '://' + media_type + '/' + media_id], request.state.cache)
    elif media_db == 'tmdb':
        media_info = await request.state.tmdb.get_media_by_id([media_db + '://' + media_type + '/' + media_id], request.state.cache)
    elif media_db == 'tvdb':
        media_info = await request.state.tvdb.get_media_by_id([media_db + '://' + media_type + '/' + media_id], request.state.cache)
    else:
        raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = 'Not Implemented')

    if not media_info:
        raise HTTPException(status_code = HTTP_404_NOT_FOUND,       detail = 'Not Found')

    media_info = media_info[0]['results'][0] if media_info and 'results' in media_info[0] else None

    return media_info
