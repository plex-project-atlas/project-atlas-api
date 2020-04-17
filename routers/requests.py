import json
import base64
import asyncio
import logging
import binascii

from   fastapi             import APIRouter, Request, Path, Query, HTTPException
from   typing              import List
from   libs.models         import RequestListObject, RequestMediaObject
from   starlette.status    import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND


router          = APIRouter()


@router.get(
    '',
    summary        = 'Retrieve users requests list',
    response_model = List[RequestListObject]
)
async def get_requests(
    request: Request,
    pendent_only: bool = Query(
        ...,
        title          = 'Pendent Only',
        description    = 'Return only pendent requests (do not show closed ones)',
    )
):
    requests = request.state.requests.get_requests_list(pendent_only)

    imdb_ids = [request['request_id'] for request in requests if request['request_id'].startswith('imdb')]
    tmdb_ids = [request['request_id'] for request in requests if request['request_id'].startswith('tmdb')]
    tvdb_ids = [request['request_id'] for request in requests if request['request_id'].startswith('tvdb')]

    media_ids = [
        request.state.tmdb.get_media_by_id(imdb_ids, request.state.cache),
        request.state.tmdb.get_media_by_id(tmdb_ids, request.state.cache),
        request.state.tvdb.get_media_by_id(tvdb_ids, request.state.cache)
    ]
    media_ids = await asyncio.gather(*media_ids)
    media_ids = [media_id for media_source in media_ids for media_id in media_source]

    for request in requests:
        media_info = [
            media_id for media_id in media_ids
            if 'query' in media_id and media_id['query'] == request['request_id']
        ]
        if media_info and 'results' in media_info[0] and media_info[0]['results']:
            request['request_info'] = media_info[0]['results'][0]

    return requests


@router.get(
    '/{request_id}',
    summary        = 'Retrieve a single request details',
    response_model = RequestMediaObject
)
async def get_request_details(
    request: Request,
    request_id: str = Path(
        ...,
        title       = 'Request ID',
        description = 'The Base64 encoded request ID string'
    )
):
    try:
        request_id = base64.b64decode(request_id).decode()
    except binascii.Error:
        logging.error('[Requests] - Submitted ID is not a valid Base64 string')
        raise HTTPException(status_code = HTTP_400_BAD_REQUEST, detail = 'Bad Request')

    if not request_id.startswith(('imdb', 'tmdb', 'tvdb')):
        raise HTTPException(status_code = HTTP_400_BAD_REQUEST, detail = 'Bad Request')

    request_info = request.state.requests.get_request(request_id)
    media_info   = await request.state.tmdb.get_media_by_id([request_id], request.state.cache) \
                   if request_id.startswith(('imdb', 'tmdb')) else \
                   await request.state.tvdb.get_media_by_id([request_id], request.state.cache)

    request_info['request_list'] = json.loads(request_info['request_list'])
    request_info['request_info'] = media_info[0]['results'][0]

    if not any([ request_info['request_list'], request_info['request_info'] ]):
        logging.error('[Requests] - Submitted ID details could be found')
        raise HTTPException(status_code = HTTP_404_NOT_FOUND, detail = 'Not Found')

    return request_info
