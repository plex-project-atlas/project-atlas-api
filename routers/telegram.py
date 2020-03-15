import logging

from   fastapi             import APIRouter, Body, Request, Response, HTTPException
from   typing              import Any
from   libs.telegram       import Statuses
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
        if action in Statuses.Help['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = Statuses.Help['message']
            )
            # clearing user status code [-1]
            request.state.telegram.register_user_status(chat_id, -1)
        elif action in Statuses.NewRequest['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = Statuses.NewRequest['message'],
                choices      = [
                    [{
                        "text": 'Un Film',
                        "callback_data": Statuses.SrcMovie['commands'][0]
                    }],
                    [{
                        "text": 'Una Serie TV',
                        "callback_data": Statuses.SrcShow['commands'][0]
                    }]
                ]
            )
            # clearing user status code [-1]
            request.state.telegram.register_user_status(chat_id, -1)
        elif action in Statuses.SrcMovie['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = Statuses.SrcMovie['message']
            )
            # updating user status code
            request.state.telegram.register_user_status(chat_id, Statuses.SrcMovie['code'])
        elif action in Statuses.SrcShow['commands']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = Statuses.SrcShow['message']
            )
            # updating user status code
            request.state.telegram.register_user_status(chat_id, Statuses.SrcShow['code'])
        else:
            logging.warning('[TG] - Unexpected, unimplemented command received: %s', action)
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = Statuses.Help['message']
            )
            # clearing user status code [-1]
            request.state.telegram.register_user_status(chat_id, -1)
        return Response(status_code = HTTP_204_NO_CONTENT)

    # generic message received, we need to retrieve user status
    if message:
        logging.info('[TG] - Message received: %s', message)
        status = request.state.telegram.get_user_status(chat_id)
        logging.info('[TG] - Status for user %s: %s', chat_id, status)

        if status == Statuses.Help['code']:
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = Statuses.Help['message']
            )
        elif status in [ Statuses.SrcMovie['code'], Statuses.SrcShow['code'] ]:
            if any(message.startswith(source) for source in ['imdb://', 'tmdb://', 'tvdb://']):
                request.state.telegram.send_message(
                    dest_chat_id = chat_id,
                    dest_message = 'Perfetto, registro subito la tua richiesta'
                )
                # clearing user status code [-1]
                request.state.telegram.register_user_status(chat_id, -1)
                return Response(status_code = HTTP_204_NO_CONTENT)

            if message == 'online://not-found':
                request.state.telegram.send_message(
                    dest_chat_id = chat_id,
                    dest_message = 'Mi dispiace, prova a ridirmi il titolo'
                )
                return Response(status_code = HTTP_204_NO_CONTENT)

            if not message.startswith('plex://'):
                plex_results   = request.state.plex.search_media_by_name([message.strip()], 'movie') \
                                 if status == Statuses.SrcMovie['code'] else \
                                 request.state.plex.search_media_by_name([message.strip()], 'show')
            elif not message.startswith('plex://not-found/'):
                request.state.telegram.send_message(
                    dest_chat_id = chat_id,
                    dest_message = 'Ottimo, allora ti auguro buona visione\\!'
                )
                # clearing user status code [-1]
                request.state.telegram.register_user_status(chat_id, -1)
                return Response(status_code = HTTP_204_NO_CONTENT)

            online_results = []
            if not plex_results or not plex_results[0]['results'] or message.startswith('plex://not-found/'):
                request.state.telegram.send_message(
                    dest_chat_id = chat_id,
                    dest_message = 'Ottimo, faccio subito una ricerca online'
                )
                search_title = message.replace('plex://not-found/', '') if message.startswith('plex://not-found/') \
                               else message
                online_results = await request.state.tmdb.search_movie_by_name([search_title], 'movie') \
                                 if status == Statuses.SrcMovie['code'] else \
                                 await request.state.tvdb.search_show_by_name([search_title], 'show')
                if not online_results or not online_results[0]['results']:
                    request.state.telegram.send_message(
                        dest_chat_id = chat_id,
                        dest_message = 'Mi dispiace ma non ho trovato nulla, prova a ridirmi il titolo'
                    )
                    return Response(status_code = HTTP_204_NO_CONTENT)

            choices = [ [{
                "text":          elem['title'] + ' (' + elem['year'] + ')',
                "callback_data": elem['guid']
            }] for elem in (
                plex_results[0]['results'][:5]
                if plex_results and plex_results[0]['results'] else
                online_results[0]['results'][:5]
            ) ]
            choices.append([{
                "text":          'Nessuno di questi',
                "callback_data": 'online://not-found'
                                 if online_results and online_results[0]['results'] else
                                 'plex://not-found/' + message
            }])
            request.state.telegram.send_message(
                dest_chat_id = chat_id,
                dest_message = 'Ho trovato questi titoli' +
                               (' nella libreria di Plex, ' if plex_results and plex_results[0]['results']  else ', ') +
                               'è per caso uno di loro?',
                choices      = choices
            )
            # updating user status code
            #request.state.telegram.register_user_status(
            #    chat_id,
            #    Statuses.SrcMovie['code'] + 1 if status == Statuses.SrcMovie['code'] else Statuses.SrcShow['code'] + 1
            #)
        else:
            logging.info('[TG] - Still not implemented')
        return Response(status_code = HTTP_204_NO_CONTENT)

    # fallback ending
    return Response(status_code = HTTP_204_NO_CONTENT)
