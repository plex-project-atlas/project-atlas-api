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
        'code':  -1,
        'commands': ['/start', '/help'],
        'message':  'Ciao sono _*Plexa*_, la tua assistente virtuale 😊\n\n' + \
                    'Sono qui per aiutarti a gestire le tue richieste, che contribuiscono a migliorare' + \
                    'l\'esperienza di Plex per tutti gli utenti\\.\n\n' + \
                    'Questa è la lista di tutte le cose che posso fare:\n\n' + \
                    '/help - Ti riporta a questo menù\n' + \
                    '/newRequest - Richiedi una nuova aggiunta a Plex' + \
                    '/myRequests - Accedi alla lista delle tue richieste'
    }
    NewRequest = {
        'code': 100,
        'commands': ['/newRequest'],
        'message':  'Stai cercando un Film o una Serie TV\\?'
    }
    # Intro      = { 'code':  -1, 'keywords': ['/Start', 'Aiuto']  }
    # Menu       = { 'code':   0, 'keywords': ['Menù']             }
    # NewRequest = { 'code': 100, 'keywords': ['Nuova Richiesta']  }
    # MyRequests = { 'code': 200, 'keywords': ['Le Mie Richieste'] }
    # SrcMovie   = { 'code': 110, 'keywords': ['Un Film']          }
    # SrcShow    = { 'code': 120, 'keywords': ['Una Serie TV']     }


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment',
    status_code    = HTTP_204_NO_CONTENT,
    response_model = None
)
async def plexa_answer( request: Request, payload: Any = Body(...) ):
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

    def register_user_status(user_id, current_status, new_status: int):
        query = '''
            INSERT project_atlas.tg_user_status (user, status)
            VALUES (%USER_ID%, %USER_STATUS%)
        ''' if current_status is None else '''
            UPDATE project_atlas.tg_user_status
            SET    status = %USER_STATUS%
            WHERE  user = %USER_ID%
        '''
        query     = query.replace( '%USER_ID%', str(user_id) ).replace( '%USER_STATUS%', str(new_status) )
        query_job = request.state.bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        results   = query_job.result()
        return None if not results else results.total_rows

    def send_message(
            callback_query_id: int  = None,
            dest_chat_id:      int  = None,
            dest_message:      str  = None,
            img:               str  = None,
            choices:      List[str] = None
    ):
        response = {}
        headers  = {'Content-Type': 'application/json'}
        if callback_query_id:
            response['callback_query_id'] = callback_query_id
        else:
            response['parse_mode'] = 'MarkdownV2'
        if chat_id:
            response['chat_id'] = dest_chat_id
        if img:
            response['photo']   = img
            response['caption'] = dest_message
        elif not callback_query_id:
            response['text']    = dest_message
        if choices:
            response['reply_markup'] = {
                'keyboard': [ [{ 'text': choice }] for choice in choices ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }

        tg_api_endpoint = 'answerCallbackQuery' if callback_query_id else '/sendPhoto' if img else '/sendMessage'
        send_response   = httpx.post(
            tg_api_base_url + tg_bot_token + tg_api_endpoint,
            json    = response,
            headers = headers
        )
        if send_response.status_code != HTTP_200_OK:
            logging.error('[TG] - Error sending message: %s', response)
            raise HTTPException(status_code = send_response.status_code, detail = 'Unable To Reply To Telegram Chat')

    logging.info('[TG] - Update received: %s', payload)

    if 'callback_query' in payload:
        # immediately answer to callback request and close it
        send_message(callback_query_id = payload['callback_query']['id'])
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

    #status  = get_user_status(user_id)
    #logging.info('[TG] - Current status for user %d: %s', user_id, status)

    if action and action in Statuses.Help['commands']:
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.Help['message']
        )
    elif action and action in Statuses.NewRequest['commands']:
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.NewRequest['message']
        )
    else:
        send_message(
            dest_chat_id = chat_id,
            dest_message = Statuses.Help['message']
        )

    return Response(status_code = HTTP_204_NO_CONTENT)
