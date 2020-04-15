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
    def send_and_register(status: int, msg_text: str, msg_choices: List[ List[dict] ] = None):
        request.state.telegram.send_message(
            dest_chat_id = chat_id,
            dest_message = msg_text,
            choices      = msg_choices if msg_choices else None
        )
        request.state.telegram.set_user_status(chat_id, status)

    logging.info('[TG] - Update received: %s', payload)
    if not any(update in payload for update in ['message', 'callback_query']):
        logging.error('[TG] - Unexpected, unimplemented update received')
        raise HTTPException(status_code = HTTP_501_NOT_IMPLEMENTED, detail = 'Not Implemented')

    # extracting telegram's update action or message
    action, chat_id, message = None, None, None
    if 'callback_query' in payload:
        # immediately answer to callback request and close it
        request.state.telegram.send_message(callback_query_id = payload['callback_query']['id'])
        logging.info('[TG] - Answering callback query: %s', payload['callback_query']['id'])
        chat_id = payload['callback_query']['message']['chat']['id']
        action  = payload['callback_query']['data']
    elif 'message' in payload:
        chat_id = payload['message']['chat']['id']
        message = payload['message']['text'].strip().lower()
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
        logging.error('[TG] - Unable to process update data (Chat: %s, Command: %s, Message: %s)',
                      chat_id, action, message)
        raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

    if action:
        logging.info('[TG] - Command received: %s', action)
        if action not in request.state.telegram.tg_action_tree:
            logging.warning('[TG] - Unexpected, no action defined for command: %s', action)
            action = '/help'

        send_and_register(
            status      = request.state.telegram.tg_action_tree[action]['status_code'],
            msg_text    = request.state.telegram.tg_action_tree[action]['message'],
            msg_choices = request.state.telegram.tg_action_tree[action]['choices']
                          if 'choices' in request.state.telegram.tg_action_tree[action] else None
        )
        return Response(status_code = HTTP_204_NO_CONTENT)

    # generic message received, we need to retrieve user status
    user_status  = request.state.telegram.get_user_status(chat_id)
    if message:
        logging.info('[TG] - Message received: %s', message)
        logging.info('[TG] - Status for user %s: %s', chat_id, user_status)

        choices = None

        # random message, redirect to intro
        if user_status == request.state.telegram.tg_action_tree['/help']['status_code']:
            action = '/help'
        # specific plex id received, media is already present and there's not need for a new request
        elif message.startswith('plex') and 'not-found' not in message:
            action = 'plex://found'
        # media found online, registering request
        elif message.startswith(('imdb', 'tmdb', 'tvdb')) and 'not-found' not in message:
            action = 'online://found'
        # media not found online, repeating request
        elif message.startswith('online://not-found'):
            action = 'online://not-found'
        # no direct exit case, proceeding with media search
        elif user_status in [ request.state.telegram.tg_action_tree[key]['status_code']
                              for key in request.state.telegram.tg_action_tree if key in ['/srcMovie', '/srcShow'] ]:
            search_title, plex_results, online_results = '', [], []
            media_type = 'movie' if user_status == request.state.telegram.tg_action_tree['/srcMovie']['status_code'] else 'show'
            # skip plex search if already done
            if not message.startswith('plex://not-found'):
                action       = 'plex://results'
                search_title = message
                plex_results = request.state.plex.search_media_by_name([message.strip()], media_type) \
                               if media_type == 'movie' else \
                               request.state.plex.search_media_by_name([message.strip()], media_type)
                plex_results = plex_results[0]['results'] if plex_results and plex_results[0]['results'] else []
            elif not plex_results:
                action       = 'online://results'
                search_title = message.replace('plex://not-found', '')
                media_search = request.state.tmdb.search_media_by_name \
                               if user_status == request.state.telegram.tg_action_tree['/srcMovie']['status_code'] else \
                               request.state.tvdb.search_media_by_name
                request.state.telegram.send_message(
                    dest_chat_id = chat_id,
                    dest_message = 'Ottimo, faccio subito una ricerca online'
                )
                online_results = await media_search([{'title': search_title, 'type':  media_type}], request.state.cache)
                online_results = online_results[0]['results'] if online_results and online_results[0]['results'] else []

            choices = request.state.telegram.build_paginated_choices(
                'plex://' + media_type + 'search/' + search_title if plex_results else
                ( ('tmdb://' if media_type == 'movie' else 'tvdb://') + media_type + '/search/' + search_title),
                [ {
                    'text': emoji.emojize( '{icon} {title} ({year})'.format(
                        title = result['title'],
                        year  = (result['year'] if result['year'] else 'N/D'),
                        icon  = ':movie_camera:' if media_type == 'movie' else ':clapper_board:'
                    ) ),
                    'link': result['guid']
                } for result in (plex_results if plex_results else online_results) ]
            )
        else:
            logging.warning( '[TG] - User status code not yet implemented: %s', str(user_status) )

        request.state.telegram.send_message(
            dest_chat_id = chat_id,
            dest_message = request.state.telegram.tg_action_tree[action]['message'],
            choices      = choices if choices else request.state.telegram.tg_action_tree[action]['choices']
                           if 'choices' in request.state.telegram.tg_action_tree[action] else None
        )
        if 'status_code' in request.state.telegram.tg_action_tree[action]:
            request.state.telegram.set_user_status(chat_id, request.state.telegram.tg_action_tree[action]['status_code'])

        return Response(status_code = HTTP_204_NO_CONTENT)

    # fallback ending
    return Response(status_code = HTTP_204_NO_CONTENT)
