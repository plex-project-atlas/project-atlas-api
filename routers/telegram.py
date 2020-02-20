import os
import httpx
import logging

from   fastapi             import APIRouter, Body, HTTPException
from   google.cloud        import bigquery
from   typing              import Any
from   starlette.status    import HTTP_200_OK, \
                                  HTTP_204_NO_CONTENT


router          = APIRouter()
bq              = bigquery.Client()
tg_bot_token    = os.environ.get('TG_BOT_TOKEN')
tg_api_base_url = 'https://api.telegram.org/bot'


class Statuses(dict):
    Welcome    = { 'code': -1, 'text': '/Start' }
    Help       = { 'code': -1, 'text': 'Aiuto'  }
    Menu       = { 'code':  0, 'text': 'Menù'   }
    NewRequest = { 'code':  1, 'text': 'Nuova Richiesta' }
    MyRequests = { 'code':  2, 'text': 'Le Mie Richieste' }
    SrcMovie   = { 'code':  3, 'text': 'Un Film' }
    SrcShow    = { 'code':  4, 'text': 'Una Serie TV' }


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment',
    status_code    = HTTP_204_NO_CONTENT
)
async def plexa_answer( payload: Any = Body(...) ):
    def get_user_status(user_id: int):
        query = """
            SELECT status
            FROM   project_atlas.tg_user_status
            WHERE  user = %USER_ID%
        """
        query     = query.replace( '%USER_ID%', str(user_id) )
        query_job = bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
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
        query = query.replace( '%USER_ID%', str(user_id) ).replace( '%USER_STATUS%', str(new_status) )
        query_job = bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        results = query_job.result()

    logging.info('[TG] - Update received: %s', payload)

    status    = get_user_status(payload['message']['from']['id'])
    headers   = { 'Content-Type': 'application/json' }
    responses = {
        Statuses.Welcome['code']: {
            "chat_id": payload['message']['from']['id'],
            "photo": "https://storage.googleapis.com/plex-api/icons/bulma_help.png",
            "caption": "Ciao sono _*Plexa*_, la tua assistente virtuale 😊\n\n" + \
                       "Sono qui per aiutarti a gestire le tue richieste, che contribuiscono a migliorare" + \
                       "l'esperienza di Plex per tutti gli utenti\\.\n\n" + \
                       "Scegli l'azione desiderata e ti guiderò nel completamento della tua richiesta\\!",
            "parse_mode": "MarkdownV2",
            "reply_markup": {
                "keyboard": [
                    [{
                        "text": Statuses.NewRequest['text']
                    }],
                    [{
                        "text": Statuses.MyRequests['text']
                    }]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        },
        Statuses.Menu['code']: {
            "chat_id": payload['message']['from']['id'],
            "text": "Ciao\\! Come posso aiutarti oggi\\?",
            "parse_mode": "MarkdownV2",
            "reply_markup": {
                "keyboard": [
                    [{
                        "text": Statuses.NewRequest['text']
                    }],
                    [{
                        "text": Statuses.MyRequests['text']
                    }]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        },
        Statuses.NewRequest['code']: {
            "chat_id": payload['message']['from']['id'],
            "text": "Benissimo, cosa vorresti aggiungere\\?",
            "parse_mode": "MarkdownV2",
            "reply_markup": {
                "keyboard": [
                    [{
                        "text": Statuses.SrcMovie['text']
                    }],
                    [{
                        "text": Statuses.SrcShow['text']
                    }]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        }
    }
    logging.info('[TG] - Current status for user %d: %s', payload['message']['from']['id'], status)

    action = payload['message']['text'].strip().lower()

    if action in [Statuses.Welcome['text'].lower(), Statuses.Help['text'].lower()]:
        tg_api_endpoint = '/sendPhoto'
        response        = responses[ Statuses.Welcome['code'] ]
        send_response   = httpx.post(
            tg_api_base_url + tg_bot_token + tg_api_endpoint,
            json    = response,
            headers = headers
        )
        if send_response.status_code != HTTP_200_OK:
            raise HTTPException(status_code = send_response.status_code, detail = 'Unable To Reply To Telegram Chat')
        register_user_status(payload['message']['from']['id'], status, Statuses.Welcome['code'])
        return None
