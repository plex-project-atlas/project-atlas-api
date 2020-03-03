import os
import httpx
import logging

from   fastapi             import APIRouter, Body, HTTPException
from   typing              import Any, List
from   starlette.requests  import Request
from   starlette.responses import Response
from   starlette.status    import HTTP_200_OK, \
                                  HTTP_204_NO_CONTENT


router          = APIRouter()
tg_bot_token    = os.environ.get('TG_BOT_TOKEN')
tg_api_base_url = 'https://api.telegram.org/bot'


class Statuses(dict):
    Help = {
        'code':     -1,
        'commands': ['/start', '/help'],
        'message':  'Ciao sono _*Plexa*_, la tua assistente virtuale 😊\n\n' + \
                    'Sono qui per aiutarti a gestire le tue richieste, che contribuiscono a migliorare ' + \
                    'l\'esperienza di Plex per tutti gli utenti\\.\n\n' + \
                    'Questa è la lista di tutte le cose che posso fare:\n\n' + \
                    '/help \\- Ti riporta a questo menù\n' + \
                    '/newRequest \\- Richiedi una nuova aggiunta a Plex\n' + \
                    '/myRequests \\- Accedi alla lista delle tue richieste'
    }
    NewRequest = {
        'code':     100,
        'commands': ['/newRequest'],
        'message':  'Stai cercando un Film o una Serie TV\\?'
    }
    SrcMovie = {
        'code':     110,
        'commands': ['/srcMovie'],
        'message':  'Vai, spara il titolo\\!'
    }
    SrcShow = {
        'code':     120,
        'commands': ['/srcShow'],
        'message': 'Vai, spara il titolo\\!'
    }


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment',
    status_code    = HTTP_204_NO_CONTENT,
    response_model = None
)
async def plexa_answer( request: Request, payload: Any = Body(...) ):
    def register_user_status(user_id, new_status: int):
        query = '''
            DELETE FROM project_atlas.tg_user_status WHERE user = %USER_ID%;
            INSERT project_atlas.tg_user_status (user, status) VALUES (%USER_ID%, %USER_STATUS%);
        '''
        query     = query.replace( '%USER_ID%', str(user_id) ).replace( '%USER_STATUS%', str(new_status) )
        query_job = request.state.bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        results   = query_job.result()
        return None if not results else results.total_rows

    def get_user_status(user_id: int):
        query = """
            SELECT status
            FROM   project_atlas.tg_user_status
            WHERE  user = %USER_ID%
        """
        query     = query.replace( '%USER_ID%', str(user_id) )
        query_job = request.state.bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        results   = query_job.result()
        return None if results.total_rows == 0 else next( iter(results) )['status']

    def send_message(
            callback_query_id:  str   = None,
            dest_chat_id:       str   = None,
            dest_message:       str   = None,
            img:                str   = None,
            choices: List[List[dict]] = None
    ):
        response = {}
        headers  = {'Content-Type': 'application/json'}
        if callback_query_id:
            response['callback_query_id'] = callback_query_id
        else:
            response['parse_mode'] = 'MarkdownV2'
        if dest_chat_id:
            response['chat_id'] = dest_chat_id
        if img:
            response['photo']   = img
            response['caption'] = dest_message
        elif not callback_query_id:
            response['text']    = dest_message
        if choices:
            response['reply_markup'] = {
                'inline_keyboard': choices
            }

        tg_api_endpoint = '/answerCallbackQuery' if callback_query_id else '/sendPhoto' if img else '/sendMessage'
        send_response   = httpx.post(
            tg_api_base_url + tg_bot_token + tg_api_endpoint,
            json    = response,
            headers = headers
        )
        if send_response.status_code != HTTP_200_OK:
            logging.error('[TG] - Error sending message (%s): %s', tg_api_endpoint, response)
            raise HTTPException(status_code = send_response.status_code, detail = 'Unable To Reply To Telegram Chat')

    logging.info('[TG] - Update received: %s', payload)

    if 'callback_query' in payload:
        # immediately answer to callback request and close it
        send_message(callback_query_id = payload['callback_query']['id'])
        logging.info('Sent an answer to callback query %s', payload['callback_query']['id'])
        action   = payload['callback_query']['data']
    elif 'entities' in payload['message']:
        commands = [command for command in payload['message']['entities'] if command['type'] == 'bot_command']
        if len(commands) > 1:
            logging.warning('[TG] - Multiple bot commands received, keeping only the first one')
        action   = payload['message']['text'][ commands[0]['offset']:commands[0]['length'] ]
    else:
        action   = None
    message = payload['message']['text'].strip().lower()
    chat_id = payload['message']['chat']['id']

    logging.info('[TG] - Updated received - Chat: %s, Message: %s, Command: %s',
                 chat_id, message, action if action else 'None')

    # not callback action nor command, we need to parse previous status
    if not action:
        status  = get_user_status(chat_id)
        logging.info('[TG] - Current status for user %d: %s', chat_id, status)

        if not status:
            send_message(
                dest_chat_id = chat_id,
                dest_message = Statuses.Help['message']
            )
        # 110 - New Movie
        elif status == 110:
            plex_results = request.state.plex.search_media_by_name(message.strip().replace(',', ''), 'movie')
            send_message(
                dest_chat_id = chat_id,
                choices      = [
                    [{
                        "text":          elem['title'] + ' (' + elem.year + ')',
                        "callback_data": elem['guid']
                    }] for elem in plex_results[0]['results']
                ]
            )
        # 120 - New Show
        elif status == 120:
            plex_results = request.state.plex.search_media_by_name(message.strip().replace(',', ''), 'show')
            send_message(
                dest_chat_id = chat_id,
                choices      = [
                    [{
                        "text":          elem['title'] + ' (' + elem.year + ')',
                        "callback_data": elem['guid']
                    }] for elem in plex_results[0]['results']
                ]
            )

        return None

    if action in Statuses.Help['commands']:
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.Help['message']
        )
    elif action in Statuses.NewRequest['commands']:
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.NewRequest['message'],
            choices      = [
                [{ "text": "Un Film",      "callback_data": Statuses.SrcMovie['commands'][0] }],
                [{ "text": "Una Serie TV", "callback_data": Statuses.SrcShow['commands'][0]  }]
            ]
        )
    elif action in Statuses.SrcMovie['commands']:
        register_user_status(chat_id, Statuses.SrcMovie['code'])
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.SrcMovie['message']
        )
    elif action in Statuses.SrcShow['commands']:
        register_user_status(chat_id, Statuses.SrcShow['code'])
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.SrcShow['message']
        )
    else:
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.Help['message']
        )

    return Response(status_code = HTTP_204_NO_CONTENT)
