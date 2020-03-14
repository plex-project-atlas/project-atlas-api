import os
import httpx
import logging

from   fastapi             import HTTPException
from   typing              import List
from   google.cloud        import bigquery
from   starlette.status    import HTTP_200_OK


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


class TelegramClient:
    def __init__(self):
        self.bq_client       = bigquery.Client()
        self.tg_bot_token    = os.environ.get('TG_BOT_TOKEN')
        self.tg_api_base_url = 'https://api.telegram.org/bot'

    def register_user_status(self, user_id, new_status: int):
        query = '''
            DELETE FROM project_atlas.tg_user_status WHERE user = %USER_ID%;
            INSERT project_atlas.tg_user_status (user, status) VALUES (%USER_ID%, %USER_STATUS%);
        '''
        query       = query.replace( '%USER_ID%', str(user_id) ).replace( '%USER_STATUS%', str(new_status) )
        query_job   = self.bq_client.query(query, project=os.environ['DB_PROJECT'], location=os.environ['DB_REGION'])
        try:
            results = query_job.result()
        except:
            logging.error('[BQ] - Error registering user status')
            results  = None
        return None if not results else results.total_rows

    def get_user_status(self, user_id: int):
        query = """
            SELECT status
            FROM   project_atlas.tg_user_status
            WHERE  user = %USER_ID%
        """
        query       = query.replace( '%USER_ID%', str(user_id) )
        query_job   = self.bq_client.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        try:
            results = query_job.result()
        except:
            logging.error('[BQ] - Error retrieving user status')
            results = None
        return -1 if not results or results.total_rows == 0 else next( iter(results) )['status']

    def send_message(
            self,
            callback_query_id:  int   = None,
            dest_chat_id:       int   = None,
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

        tg_api_endpoint = 'answerCallbackQuery' if callback_query_id else '/sendPhoto' if img else '/sendMessage'
        send_response   = httpx.post(
            self.tg_api_base_url + self.tg_bot_token + tg_api_endpoint,
            json    = response,
            headers = headers
        )
        if send_response.status_code != HTTP_200_OK:
            error_message = None
            try:
                error_message = send_response.json()
                logging.error('[TG] - Error sending message: %s', error_message['description'])
            except:
                logging.error('[TG] - Error sending message: %s', response)
            raise HTTPException(
                status_code = send_response.status_code,
                detail = error_message['description'] if error_message else response
            )
