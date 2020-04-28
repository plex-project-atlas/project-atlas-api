import re
import math
import emoji
import asyncio
import logging

from   fastapi             import APIRouter, Body, Request, Response, HTTPException
from   libs.models         import Request as RequestPayload
from   typing              import Any
from   starlette.status    import HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND


router          = APIRouter()


def get_user_request_page(request: Request, user_id: int, pendent_only = True, page = 1):
    choices = request.state.requests.get_requests_list(pendent_only = pendent_only, user_id = user_id)
    media_details = [
        request.state.tmdb.get_media_by_id(
            [ choice['request_id'] for choice in choices if 'movie' in choice['request_id'] ],
            request.state.cache
        ),
        request.state.tvdb.get_media_by_id(
            [ choice['request_id'] for choice in choices if 'show' in choice['request_id'] ],
            request.state.cache
        )
    ]
    media_details = await asyncio.gather(*media_details)
    media_details = [
        media['results'][0] for media_type in media_details for media in media_type if media['results']
    ]
    for choice in choices:
        media_info = [ media for media in media_details if media['guid'] == choice['request_id'] ][0]
        choice['request_info'] = media_info

    choices = request.state.telegram.build_paginated_choices(
        page_key = 'requests://{user_id}{filter}'.format(user_id = user_id, filter = '/all' if not pendent_only else ''),
        elements = [{
            'text': emoji.emojize( '{status} {icon} - {title} ({year}){season}'.format(
                status = ':yellow_circle:' if choice['request_status'] == 'WAIT' else \
                         ':green_circle:'  if choice['request_status'] == 'OK'   else \
                         ':red_circle:'    if choice['request_status'] == 'KO'   else ':blue_circle:',
                icon   = ':movie_camera:'  if 'movie' in choice['request_id']    else ':clapper_board:',
                title  = choice['request_info']['title'],
                year   = choice['request_info']['year'] if choice['request_info']['year'] else 'N/D',
                season = ' - Stagione {}'.format(choice['request_season']) if choice['request_season'] > 0 else
                         ' - Speciali'   if choice['request_season'] == 0  else ''
            ) ),
            'link': 'requests://{user_id}/'.format(user_id = user_id)
        } for choice in choices],
        page         = page,
        extra_choice = {
            'text': 'Mostra richieste chiuse',
            'link': 'requests://{user_id}/all/p1'.format(user_id = user_id)
        } if not pendent_only else None
    )
    return choices


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment',
    status_code    = HTTP_204_NO_CONTENT,
    response_model = None
)
async def plexa_answer( request: Request, payload: Any = Body(...) ):
    logging.info('[TG] - Update received: %s', payload)
    if not any(update in payload for update in ['message', 'callback_query']):
        logging.warning('[TG] - Unexpected, unimplemented update received')
        return Response(status_code = HTTP_204_NO_CONTENT)

    # extracting telegram's update action or message
    action, user_id, user_name, user_first_name, user_last_name, choices, message = None, None, None, None, None, None, None
    if 'callback_query' in payload:
        # immediately answer to callback request and close it
        request.state.telegram.send_message(callback_query_id = payload['callback_query']['id'])
        logging.info('[TG] - Answering callback query: %s', payload['callback_query']['id'])
        action  = payload['callback_query']['data']
        user_id = payload['callback_query']['from']['id']
        user_name       = payload['callback_query']['from']['username'] \
                          if 'username' in payload['callback_query']['from']   else None
        user_last_name  = payload['callback_query']['from']['last_name'] \
                          if 'last_name' in payload['callback_query']['from']  else None
        user_first_name = payload['callback_query']['from']['first_name'] \
                          if 'first_name' in payload['callback_query']['from'] else None
    elif 'message' in payload:
        user_id = payload['message']['from']['id']
        message = payload['message']['text'].strip().lower() if 'text' in payload['message'] else ''
        user_name       = payload['message']['from']['username']   \
            if 'username' in payload['message']['from'] else None
        user_last_name  = payload['message']['from']['last_name']  \
            if 'last_name' in payload['message']['from'] else None
        user_first_name = payload['message']['from']['first_name'] \
            if 'first_name' in payload['message']['from'] else None
        if 'entities' in payload['message']:
            commands = [command for command in payload['message']['entities'] if command['type'] == 'bot_command']
            if len(commands) > 1:
                logging.warning('[TG] - Multiple bot commands received, keeping only the first one')
            if len(commands) > 0:
                action = payload['message']['text'][ commands[0]['offset']:commands[0]['length'] ]

    # forwarding consecutive actions to message handling
    if action and not action.startswith('/'):
        message = action
        action  = None

    if not user_id or not any([action, message]) \
    or ( message and '://' in message and not message.startswith(('requests', 'plex', 'imdb', 'tmdb', 'tvdb')) ):
        logging.warning('[TG] - Unable to process message data, falling back to intro')
        action = '/help'

    if action:
        logging.info('[TG] - Command received: %s', action)
        if action not in request.state.telegram.tg_action_tree:
            logging.warning('[TG] - Unexpected, no action defined for command: %s', action)
            action = '/help'

        if action == '/myRequests':
            choices = get_user_request_page(request, user_id)

        message_id = request.state.telegram.send_message(
            dest_chat_id = user_id,
            dest_message = request.state.telegram.tg_action_tree[action]['message'],
            choices      = choices if choices   else request.state.telegram.tg_action_tree[action]['choices']
                                   if 'choices' in   request.state.telegram.tg_action_tree[action] else None
        )
        request.state.telegram.set_user_status(user_id, request.state.telegram.tg_action_tree[action]['status_code'], message_id)
        return Response(status_code = HTTP_204_NO_CONTENT)

    # generic message received, we need to retrieve user status
    user_status = request.state.telegram.get_user_status(user_id)['user_status']
    if message:
        logging.info('[TG] - Message received: %s', message)
        logging.info('[TG] - Status for user %s: %s', user_id, user_status)

        pending_db_ops = None
        media_page = re.search("^(?:plex|imdb|tmdb|tvdb):\/\/(?:movie|show)\/search\/.+?\/p(\d+)$", message)
        if media_page and int( media_page.group(1) ) == 0:
            return Response(status_code = HTTP_204_NO_CONTENT)
        # request for user requests page
        if message.startswith('requests://') and media_page:
            choices = get_user_request_page( request, user_id, True,  int( media_page.group(1) ) ) \
                      if '/all/' in message else \
                      get_user_request_page( request, user_id, False, int( media_page.group(1) ) )
        # random message, redirect to intro
        elif user_status == request.state.telegram.tg_action_tree['/help']['status_code']:
            action = '/help'
        # specific plex id received, media is already present and there's not need for a new request
        elif message.startswith('plex') and 'not-found' not in message:
            action = 'plex://found'
        # media found online, registering request
        elif message.startswith(('imdb', 'tmdb', 'tvdb')) and 'not-found' not in message and not media_page:
            media_season = re.search("^(?:plex|imdb|tmdb|tvdb):\/\/(?:movie|show)\/.+?\/s(\d+)$", message)
            if 'show' in message and not media_season:
                media_search = request.state.tmdb.get_media_by_id if message.startswith('tmdb') else \
                               request.state.tvdb.get_media_by_id
                media_search = await media_search(
                    media_ids   = [message],
                    media_cache = request.state.cache,
                    info_only   = False
                )
                media_search = media_search[0]['results'][0]
                choices_rows = math.ceil(len(media_search['seasons']) - 1 / 5)
                choices      = []
                for i in range(0, choices_rows):
                    choices.append([])
                    for y in range(i * 5 + 1, i * 5 + 6):
                        if y > len(media_search['seasons']) - 1:
                            break
                        choices[-1].append({
                            'text':          str(y),
                            'callback_data': message + '/s' + str(y)
                        })
                if len(media_search['seasons']) - 1 > 1:
                    choices.append([{
                        'text':          'Tutte',
                        'callback_data': message + '/s0'
                    }])
                action = 'online://seasons'
            else:
                action = 'online://found'
                pending_db_ops = request.state.requests.insert_request( RequestPayload(
                    request_id      = message if not media_season else message.replace('/s' + media_season.group(1), ''),
                    user_id         = user_id,
                    user_name       = user_name,
                    user_first_name = user_first_name,
                    user_last_name  = user_last_name,
                    request_season  = int( media_season.group(1) ) if int( media_season.group(1) ) > 0 else -1
                ) )
        # media not found online, repeating request
        elif message.startswith(('imdb', 'tmdb', 'tvdb')) and 'not-found' in message:
            action = 'online://not-found'
        # user has not yet choose between movie and show
        elif user_status == request.state.telegram.tg_action_tree['/newRequest']['status_code']:
            action = '/newRequest'
        # no direct exit case, proceeding with media search
        elif user_status in [ request.state.telegram.tg_action_tree[key]['status_code']
                              for key in request.state.telegram.tg_action_tree if key in ['/srcMovie', '/srcShow'] ]:
            search_title, plex_results, online_results = '', [], []
            media_type = 'movie' if user_status == request.state.telegram.tg_action_tree['/srcMovie']['status_code'] else 'show'
            # skip plex search if already done
            if '://' not in message or (message.startswith('plex') and media_page):
                action       = 'plex://results'
                search_title = message if not media_page else message.split('/')[-2]
                try:
                    plex_results = request.state.plex.search_media_by_name([message.strip()], media_type, request.state.cache)
                except HTTPException as e:
                    if e.status_code != HTTP_404_NOT_FOUND:
                        raise e
                    plex_results = []
                plex_results = plex_results[0]['results'] if plex_results and plex_results[0]['results'] else []
            if not plex_results:
                action       = 'online://results'
                search_title = message.split('/')[-1] if not media_page else message.split('/')[-2]
                media_search = request.state.tmdb.search_media_by_name \
                               if user_status == request.state.telegram.tg_action_tree['/srcMovie']['status_code'] else \
                               request.state.tvdb.search_media_by_name
                if not media_page:
                    request.state.telegram.send_message(
                        dest_chat_id = user_id,
                        dest_message = 'Ottimo, faccio subito una ricerca online'
                    )
                try:
                    online_results = await media_search([{'title': search_title, 'type':  media_type}], request.state.cache)
                except HTTPException as e:
                    if e.status_code != HTTP_404_NOT_FOUND:
                        raise e
                    online_results = []
                online_results = online_results[0]['results'] if online_results and online_results[0]['results'] else []
                if not online_results:
                    action = 'online://not-found/direct'

            page_key = ('plex://' if plex_results else 'tmdb://' if media_type == 'movie' else 'tvdb://') + \
                       media_type + '/search/' + search_title
            choices  = request.state.telegram.build_paginated_choices(
                page_key = page_key,
                elements = [ {
                    'text': emoji.emojize( '{icon} {title} ({year})'.format(
                        title = result['title'],
                        year  = (result['year'] if result['year'] else 'N/D'),
                        icon  = ':movie_camera:' if media_type == 'movie' else ':clapper_board:'
                    ) ),
                    'link': result['guid']
                } for result in (plex_results if plex_results else online_results) ],
                page          = int( media_page.group(1) ) if media_page else 1,
                extra_choice  = {
                    'text': 'Nessuno di questi',
                    'link': page_key.split('://')[0] + '://not-found/' + page_key.split('/')[-1]
                }
            )
        else:
            logging.warning( '[TG] - User status code not yet implemented: %s', str(user_status) )
            action = '/help'

        message_id = request.state.telegram.send_message(
            edit_message_id = request.state.telegram.get_user_status(user_id)['last_message_id'] if media_page else None,
            dest_chat_id    = user_id,
            dest_message    = request.state.telegram.tg_action_tree[action]['message'],
            choices         = choices if choices else request.state.telegram.tg_action_tree[action]['choices']
                              if 'choices' in request.state.telegram.tg_action_tree[action] else None
        )
        if pending_db_ops:
            await pending_db_ops
        request.state.telegram.set_user_status(
            user_id,
            request.state.telegram.tg_action_tree[action]['status_code'] if 'status_code' in
            request.state.telegram.tg_action_tree[action] else user_status,
            message_id
        )
        return Response(status_code = HTTP_204_NO_CONTENT)

    # fallback ending
    return Response(status_code = HTTP_204_NO_CONTENT)
