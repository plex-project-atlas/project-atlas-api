import asyncio
import logging

from   fastapi             import APIRouter, Request, Query
from   typing              import List
from   libs.models         import RequestObject


router          = APIRouter()


@router.get(
    '',
    summary        = 'Retrieve users requests list',
    response_model = List[RequestObject]
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

    imdb_ids = [{
        'id':     request['request_id'].split('://')[1],
        'type':   request['request_type'],
        'source': request['request_id'].split('://')[0]
    } for request in requests if request['request_id'].startswith('imdb')]

    tmdb_ids = [{
        'id':     request['request_id'].split('://')[1],
        'type':   request['request_type']
    } for request in requests if request['request_id'].startswith('tmdb')]

    tvdb_ids = [{
        'id':     request['request_id'].split('://')[1],
        'type':   request['request_type']
    } for request in requests if request['request_id'].startswith('tvdb')]

    media_ids = [
        request.state.tmdb.get_media_by_id(imdb_ids),
        request.state.tmdb.get_media_by_id(tmdb_ids),
        request.state.tvdb.get_media_by_id(tvdb_ids)
    ]
    media_ids = await asyncio.gather(*media_ids)

    for request in requests:
        media_info = [
            media_id for media_id in media_ids
            if 'query' in media_id and media_id['query'] == request['request_id'].split('://')[1]
        ]
        if media_info and 'results' in media_info[0] and media_info[0]['results']:
            request['request_info'] = media_info[0]['results'][0]

    return requests
