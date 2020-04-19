import json
import base64
import asyncio
import logging
import binascii

from   fastapi             import APIRouter, Request, Path, Query, Response, HTTPException
from   typing              import List
from   libs.models         import RequestList, RequestDetails, Request as RequestModel
from   starlette.status    import HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST


router = APIRouter()


@router.get(
    '',
    summary        = 'Retrieve users requests list',
    response_model = List[RequestList]
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
    response_model = RequestDetails
)
async def get_request(
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

    request_info   = await request.state.requests.get_request(request_id)
    media_info     = request.state.tmdb.get_media_by_id \
                     if request_id.startswith(('imdb', 'tmdb')) else \
                     request.state.tvdb.get_media_by_id
    media_info     = await media_info([request_id], request.state.cache)

    request_info['request_list'] = json.loads(request_info['request_list'])
    request_info['request_info'] = media_info[0]['results'][0]

    return request_info


@router.post(
    '',
    summary        = 'Insert a new user request',
    response_model = None
)
async def insert_request(request: Request, request_payload: RequestModel):
    result = await request.state.requests.insert_request(request_payload)
    logging.info('[Requests] - %s rows inserted correctly', result)

    return Response(status_code = HTTP_204_NO_CONTENT)


@router.patch(
    '',
    summary        = 'Patch an existing user request',
    response_model = None
)
async def patch_request(request: Request, request_payload: RequestModel):
    result = await request.state.requests.patch_request(request_payload)
    logging.info('[Requests] - %s rows patched correctly', result)

    return Response(status_code = HTTP_204_NO_CONTENT)


@router.delete(
    '',
    summary        = 'Delete an existing user request',
    response_model = None
)
async def delete_request(request: Request, request_payload: RequestModel):
    result = await request.state.requests.delete_request(request_payload)
    logging.info('[Requests] - %s rows deleted correctly', result)

    return Response(status_code = HTTP_204_NO_CONTENT)
