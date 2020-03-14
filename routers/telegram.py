import os
import httpx
import logging

from   fastapi             import APIRouter, Body, HTTPException
from   typing              import Any, List
from   starlette.requests  import Request
from   starlette.responses import Response
from   starlette.status    import HTTP_200_OK, \
                                  HTTP_204_NO_CONTENT, \
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
        request.state.telegram.send_message(callback_query_id = payload['callback_query']['id'])
        logging.info('[TG] - Answering callback query %s...', payload['callback_query']['id'])
        action   = payload['callback_query']['data']
        chat_id  = payload['callback_query']['message']['chat']['id']
    elif 'message' in payload:
        message  = payload['message']['text'].strip().lower()
        if 'entities' in payload['message']:
            commands = [command for command in payload['message']['entities'] if command['type'] == 'bot_command']
            if len(commands) > 1:
                logging.warning('[TG] - Multiple bot commands received, keeping only the first one')
            action   = payload['message']['text'][ commands[0]['offset']:commands[0]['length'] ]
            chat_id  = payload['message']['chat']['id']

    if not chat_id or not any([action, message]):
        logging.error('[TG] - Unable to process update data (Chat: %s, Command: %s, Message: %s)',
                      chat_id, action, message)
        raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

    if action:
        logging.info('[TG] - Command received: %s', action)
        if action in request.state.telegram.Statuses.Help['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = request.state.telegram.Statuses.Help['message']
            )
            # clearing user status code [-1]
            request.state.telegram.register_user_status(chat_id, -1)
        elif action in request.state.telegram.Statuses.NewRequest['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = request.state.telegram.Statuses.NewRequest['message']
            )
            # clearing user status code [-1]
            request.state.telegram.register_user_status(chat_id, -1)
        elif action in request.state.telegram.Statuses.SrcMovie['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = request.state.telegram.Statuses.SrcMovie['message']
            )
            # updating user status code
            request.state.telegram.register_user_status(chat_id, request.state.telegram.Statuses.SrcMovie['code'])
        elif action in request.state.telegram.Statuses.SrcShow['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = request.state.telegram.Statuses.SrcShow['message']
            )
            # updating user status code
            request.state.telegram.register_user_status(chat_id, request.state.telegram.Statuses.SrcShow['code'])
        else:
            logging.warning('[TG] - Unexpected, unimplemented command received: %s', action)
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = request.state.telegram.Statuses.Help['message']
            )
            # clearing user status code [-1]
            request.state.telegram.register_user_status(chat_id, -1)

    # generic message received, we need to retrieve user status
    if message:
        logging.info('[TG] - Message received: %s', message)
        status = request.state.telegram.get_user_status(chat_id)
        logging.info('[TG] - Status for user %s: %s', chat_id, status)

        if status == request.state.telegram.Statuses.Help['code']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = request.state.telegram.Statuses.Help['message']
            )
        elif status == request.state.telegram.Statuses.SrcMovie['code']:
            plex_results = request.state.plex.search_media_by_name(message.strip().replace(',', ''), 'movie')
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                choices      = [
                    [{
                        "text":          elem['title'] + ' (' + elem.year + ')',
                        "callback_data": elem['guid']
                    }] for elem in plex_results[0]['results'][:5] +
                    [{
                        "text":          'Nessuno di questi',
                        "callback_data": 'plex:not_found'
                    }]
                ]
            )
            # updating user status code
            request.state.telegram.register_user_status(chat_id, request.state.telegram.Statuses.SrcMovie['code'] + 1)
        elif status == request.state.telegram.Statuses.SrcShow['code']:
            plex_results = request.state.plex.search_media_by_name(message.strip().replace(',', ''), 'show')
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                choices      = [
                    [{
                        "text":          elem['title'] + ' (' + elem.year + ')',
                        "callback_data": elem['guid']
                    }] for elem in plex_results[0]['results'][:5] +
                    [{
                        "text":          'Nessuno di questi',
                        "callback_data": 'plex:not_found'
                    }]
                ]
            )
            # updating user status code
            request.state.telegram.register_user_status(chat_id, request.state.telegram.Statuses.SrcShow['code'] + 1)
        else:
            logging.info('[TG] - Still not implemented')

    return Response(status_code = HTTP_204_NO_CONTENT)
