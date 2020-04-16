import re
import emoji
import logging

from   fastapi             import APIRouter, Body, Request, Response, HTTPException
from   typing              import Any, List
from   starlette.status    import HTTP_204_NO_CONTENT, \
                                  HTTP_500_INTERNAL_SERVER_ERROR, \
                                  HTTP_501_NOT_IMPLEMENTED


router          = APIRouter()


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment',
    status_code    = HTTP_204_NO_CONTENT,
    response_model = None
)
async def plexa_answer( request: Request, payload: Any = Body(...) ):
    logging.info('[TG] - Update received: %s', payload)
    if not any(update in payload for update in ['message', 'callback_query']):
        logging.error('[TG] - Unexpected, unimplemented update received')
        raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = 'Not Implemented')

    # extracting telegram's update action or message
    action, chat_id, message = None, None, None
    if 'callback_query' in payload:
        # immediately answer to callback request and close it
        #request.state.telegram.send_message(callback_query_id = payload['callback_query']['id'])
        logging.info('[TG] - Answering callback query: %s', payload['callback_query']['id'])
        chat_id = payload['callback_query']['message']['chat']['id']
        action  = payload['callback_query']['data']
    elif 'message' in payload:
        chat_id = payload['message']['chat']['id']
        message = payload['message']['text'].strip().lower() if 'text' in payload['message'] else ''
        if 'entities' in payload['message']:
            commands = [command for command in payload['message']['entities'] if command['type'] == 'bot_command']
            if len(commands) > 1:
                logging.warning('[TG] - Multiple bot commands received, keeping only the first one')
            action   = payload['message']['text'][ commands[0]['offset']:commands[0]['length'] ]

    # forwarding consecutive actions to message handling
    if action and not action.startswith('/'):
        message = action
        action  = None

    if not chat_id or not any([action, message]):
        logging.warning('[TG] - Unable to process message data, falling back to intro')
        action = '/help'

    if action:
        logging.info('[TG] - Command received: %s', action)
        if action not in request.state.telegram.tg_action_tree:
            logging.warning('[TG] - Unexpected, no action defined for command: %s', action)
            action = '/help'

        message_id = request.state.telegram.send_message(
            dest_chat_id = chat_id,
            dest_message = request.state.telegram.tg_action_tree[action]['message'],
            choices      = request.state.telegram.tg_action_tree[action]['choices']
                           if 'choices' in request.state.telegram.tg_action_tree[action] else None
        )
        request.state.telegram.set_user_status(chat_id, request.state.telegram.tg_action_tree[action]['status_code'], message_id)
        return Response(status_code = HTTP_204_NO_CONTENT)

    # generic message received, we need to retrieve user status
    user_status = 110 #request.state.telegram.get_user_status(chat_id)['user_status']
    if message:
        logging.info('[TG] - Message received: %s', message)
        logging.info('[TG] - Status for user %s: %s', chat_id, user_status)

        choices    = None
        media_page = re.search("^(?:plex|imdb|tmdb|tvdb):\/\/(?:movie|show)\/search\/.+?\/p(\d+)$", message)
        if media_page and int( media_page.group(1) ) == 0:
            return Response(status_code = HTTP_204_NO_CONTENT)

        # random message, redirect to intro
        if user_status == request.state.telegram.tg_action_tree['/help']['status_code']:
            action = '/help'
        # specific plex id received, media is already present and there's not need for a new request
        elif message.startswith('plex') and 'not-found' not in message:
            action = 'plex://found'
        # media found online, registering request
        elif message.startswith(('imdb', 'tmdb', 'tvdb')) and 'not-found' not in message and not media_page:
            action = 'online://found'
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
                plex_results = request.state.plex.search_media_by_name([message.strip()], media_type) \
                               if media_type == 'movie' else \
                               request.state.plex.search_media_by_name([message.strip()], media_type)
                plex_results = plex_results[0]['results'] if plex_results and plex_results[0]['results'] else []
            if not plex_results:
                action       = 'online://results'
                search_title = message.split('/')[-1] if not media_page else message.split('/')[-2]
                media_search = request.state.tmdb.search_media_by_name \
                               if user_status == request.state.telegram.tg_action_tree['/srcMovie']['status_code'] else \
                               request.state.tvdb.search_media_by_name
                if not media_page:
                    request.state.telegram.send_message(
                        dest_chat_id = chat_id,
                        dest_message = 'Ottimo, faccio subito una ricerca online'
                    )
                online_results = await media_search([{'title': search_title, 'type':  media_type}], request.state.cache)
                online_results = online_results[0]['results'] if online_results and online_results[0]['results'] else []

            choices = request.state.telegram.build_paginated_choices(
                search_key = ('plex://' if plex_results else 'tmdb://' if media_type == 'movie' else 'tvdb://') +
                             media_type + '/search/' + search_title,
                elements   = [ {
                    'text': emoji.emojize( '{icon} {title} ({year})'.format(
                        title = result['title'],
                        year  = (result['year'] if result['year'] else 'N/D'),
                        icon  = ':movie_camera:' if media_type == 'movie' else ':clapper_board:'
                    ) ),
                    'link': result['guid']
                } for result in (plex_results if plex_results else online_results) ],
                page       = int( media_page.group(1) ) if media_page else 1
            )
        else:
            logging.warning( '[TG] - User status code not yet implemented: %s', str(user_status) )
            action = '/help'

        message_id = request.state.telegram.send_message(
            edit_message_id = request.state.telegram.get_user_status(chat_id)['last_message_id'] if media_page else None,
            dest_chat_id    = chat_id,
            dest_message    = request.state.telegram.tg_action_tree[action]['message'],
            choices         = choices if choices else request.state.telegram.tg_action_tree[action]['choices']
                              if 'choices' in request.state.telegram.tg_action_tree[action] else None
        )
        request.state.telegram.set_user_status(
            chat_id,
            request.state.telegram.tg_action_tree[action]['status_code'] if 'status_code' in
            request.state.telegram.tg_action_tree[action] else user_status,
            message_id
        )
        return Response(status_code = HTTP_204_NO_CONTENT)

    # fallback ending
    return Response(status_code = HTTP_204_NO_CONTENT)
