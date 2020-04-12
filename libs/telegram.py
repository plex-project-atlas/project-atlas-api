import os
import time
import httpx
import logging

from   fastapi             import HTTPException
from   typing              import List
from   google.cloud        import datastore
from   starlette.status    import HTTP_200_OK, \
                                  HTTP_500_INTERNAL_SERVER_ERROR


CACHE_VALIDITY = 3600


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
        self.db_client       = datastore.Client(project = 'project-atlas-tools')
        self.tg_bot_token    = os.environ.get('TG_BOT_TOKEN')
        self.tg_api_base_url = 'https://api.telegram.org/bot'

    def set_user_status(self, user_id, user_status: int):
        ds_key    = self.db_client.key('tg_user_status', user_id)
        ds_entity = datastore.Entity(key = ds_key)
        ds_entity['fill_date'] = time.time()
        ds_entity['fill_data'] = user_status

        try:
            self.db_client.put(ds_entity)
        except:
            logging.error('[TG] - Error while saving user status')
            raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

    def get_user_status(self, user_id: int):
        ds_key    = self.db_client.key('tg_user_status', user_id)
        try:
            ds_entity = self.db_client.get(key = ds_key)
        except:
            logging.error('[TG] - Error while retrieving user status')
            raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

        return ds_entity['fill_data'] if time.time() - ds_entity['fill_date'] < CACHE_VALIDITY else -1

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

        tg_api_endpoint = '/answerCallbackQuery' if callback_query_id else '/sendPhoto' if img else '/sendMessage'
        logging.info('[TG] - Calling API endpoint: %s', self.tg_api_base_url + tg_api_endpoint)
        send_response   = httpx.post(
            self.tg_api_base_url + self.tg_bot_token + tg_api_endpoint,
            json    = response,
            headers = headers
        )
        if send_response.status_code != HTTP_200_OK:
            error_message = None
            try:
                error_message = send_response.json()
                logging.error('[TG] - Error sending message, received: %s', error_message['description'])
                logging.error('[TG] - While sending payload: %s', response)
            except:
                logging.error('[TG] - Error sending message while sending payload: %s', response)
            raise HTTPException(
                status_code = send_response.status_code,
                detail = error_message['description'] if error_message else response
            )
