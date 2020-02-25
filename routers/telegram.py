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
    Intro      = { 'code':  -1, 'keywords': ['/Start', 'Aiuto']  }
    Menu       = { 'code':   0, 'keywords': ['Menù']             }
    NewRequest = { 'code': 100, 'keywords': ['Nuova Richiesta']  }
    MyRequests = { 'code': 200, 'keywords': ['Le Mie Richieste'] }
    SrcMovie   = { 'code': 110, 'keywords': ['Un Film']          }
    SrcShow    = { 'code': 120, 'keywords': ['Una Serie TV']     }


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

    def send_message(recipient: int, message: str, choices: List[str] = None, img: str = None):
        headers = {'Content-Type': 'application/json'}
        payload = {
            'chat_id': recipient,
            'parse_mode': 'MarkdownV2',
        }
        if img:
            payload['photo']   = img
            payload['caption'] = message
        else:
            payload['text']    = message
        if choices:
            payload['reply_markup'] = {
                'keyboard': [ [{ 'text': choice }] for choice in choices ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }

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
    status  = get_user_status(user_id)
    action  = payload['message']['text'].strip().lower()

    logging.info('[TG] - Current status for user %d: %s', user_id, status)

    # implementing "backwards" function
    if action == 'indietro':
        if status % 100 == 0:
            status = 0
        else:
            status = status - 10 if status % 10 == 0 else status - 1

    if action in [keyword.lower() for keyword in Statuses.Intro['keywords']]:
        send_message(
            user_id,
            message = 'Ciao sono _*Plexa*_, la tua assistente virtuale 😊\n\n' + \
                      'Sono qui per aiutarti a gestire le tue richieste, che contribuiscono a migliorare' + \
                      'l\'esperienza di Plex per tutti gli utenti\\.\n\n' + \
                      'Scegli l\'azione desiderata e ti guiderò nel completamento della tua richiesta\\!',
            choices = [
                Statuses.NewRequest['keywords'][0],
                Statuses.MyRequests['keywords'][0]
            ]
        )
        register_user_status(user_id, status, Statuses.Intro['code'])

    elif action in [keyword.lower() for keyword in Statuses.Menu['keywords']]:
        send_message(
            user_id,
            message = 'Come posso aiutarti?',
            choices = [
                Statuses.NewRequest['keywords'][0],
                Statuses.MyRequests['keywords'][0],
                Statuses.Intro['keywords'][1]
            ]
        )
        register_user_status(user_id, status, Statuses.Menu['code'])

    elif action in [keyword.lower() for keyword in Statuses.NewRequest['keywords']]:
        send_message(
            user_id,
            message = 'Stai cercando un Film o una Serie TV\\?',
            choices = [
                Statuses.SrcMovie['keywords'][0],
                Statuses.SrcShow['keywords'][0]
            ]
        )
        register_user_status(user_id, status, Statuses.NewRequest['code'])

    elif action in [keyword.lower() for keyword in Statuses.SrcMovie['keywords']]:
        send_message(
            user_id,
            message = 'Vai, spara il titolo\\!'
        )
        register_user_status(user_id, status, Statuses.SrcMovie['code'])

    elif action in [keyword.lower() for keyword in Statuses.SrcShow['keywords']]:
        send_message(
            user_id,
            message = 'Vai, spara il titolo\\!'
        )
        register_user_status(user_id, status, Statuses.SrcShow['code'])

    elif status == Statuses.SrcMovie['code']:
        results = request.state.plex.search_movie_by_name([action.replace(',', '')])
        send_message(
            user_id,
            message = 'Guarda cos\'ho trovato su Plex, è per caso uno di questi\\?',
            choices = [ result['title'] + ' (' + result['year'] + ')' for result in results[0]['results'] ] \
                    + ['Nessuno di questi']
        )

    return Response(status_code = HTTP_204_NO_CONTENT)
