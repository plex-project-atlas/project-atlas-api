import os
import httpx
import logging

from   fastapi             import APIRouter, Body, HTTPException
from   typing              import Any, List
from   google.cloud        import bigquery
from   starlette.status    import HTTP_200_OK, \
                                  HTTP_204_NO_CONTENT


router          = APIRouter()
bq              = bigquery.Client()
tg_bot_token    = os.environ.get('TG_BOT_TOKEN')
tg_api_base_url = 'https://api.telegram.org/bot'


class Statuses(dict):
    Intro      = { 'code':  -1, 'keywords': ['/Start', 'Aiuto'] }
    Menu       = { 'code':   0, 'keywords': ['Menù']   }
    NewRequest = { 'code': 100, 'keywords': ['Nuova Richiesta'] }
    MyRequests = { 'code': 200, 'keywords': ['Le Mie Richieste'] }
    SrcMovie   = { 'code': 110, 'keywords': ['Un Film'] }
    SrcShow    = { 'code': 120, 'keywords': ['Una Serie TV'] }


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment',
    status_code    = HTTP_204_NO_CONTENT
)
async def plexa_answer( payload: Any = Body(...) ):
    async def get_user_status(user_id: int):
        query = """
            SELECT status
            FROM   project_atlas.tg_user_status
            WHERE  user = %USER_ID%
        """
        query     = query.replace( '%USER_ID%', str(user_id) )
        query_job = bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        results   = query_job.result()
        return None if results.total_rows == 0 else next( iter(results) )['status']

    async def register_user_status(user_id, current_status, new_status: int):
        query = '''
            INSERT project_atlas.tg_user_status (user, status)
            VALUES (%USER_ID%, %USER_STATUS%)
        ''' if current_status is None else '''
            UPDATE project_atlas.tg_user_status
            SET    status = %USER_STATUS%
            WHERE  user = %USER_ID%
        '''
        query     = query.replace( '%USER_ID%', str(user_id) ).replace( '%USER_STATUS%', str(new_status) )
        query_job = bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        results   = query_job.result()
        return None if not results else results.total_rows

    async def send_message(recipient: int, message: str, choices: List[str], img: str = None):
        headers = {'Content-Type': 'application/json'}
        payload = {
            'chat_id': recipient,

            'parse_mode': 'MarkdownV2',
            'reply_markup': {
                'keyboard': [ [{ 'text': choice }] for choice in choices ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        }
        if img:
            payload['photo']   = img
            payload['caption'] = message
        else:
            payload['text']    = message

        tg_api_endpoint = '/sendPhoto' if img else '/sendMessage'
        send_response   = httpx.post(
            tg_api_base_url + tg_bot_token + tg_api_endpoint,
            json    = payload,
            headers = headers
        )
        if send_response.status_code != HTTP_200_OK:
            logging.error('[TG] - Error send message: %s', payload)
            raise HTTPException(status_code = send_response.status_code, detail = 'Unable To Reply To Telegram Chat')

    logging.info('[TG] - Update received: %s', payload)

    user_id = payload['message']['from']['id']
    status  = await get_user_status(user_id)
    action  = payload['message']['text'].strip().lower()

    logging.info('[TG] - Current status for user %d: %s', user_id, status)

    if action in [keyword.lower() for keyword in Statuses.Intro['keywords']]:
        await send_message(
            user_id,
            message ='Ciao sono _*Plexa*_, la tua assistente virtuale 😊\n\n' + \
                      'Sono qui per aiutarti a gestire le tue richieste, che contribuiscono a migliorare' + \
                      'l\'esperienza di Plex per tutti gli utenti\\.\n\n' + \
                     'Scegli l\'azione desiderata e ti guiderò nel completamento della tua richiesta\\!',
            choices = [
                Statuses.NewRequest['keywords'][0],
                Statuses.MyRequests['keywords'][0]
            ]
        )
        await register_user_status(user_id, status, Statuses.Intro['code'])
