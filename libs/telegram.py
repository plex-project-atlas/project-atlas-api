import os
import math
import time
import httpx
import logging

from   fastapi             import HTTPException
from   typing              import List
from   google.cloud        import datastore
from   starlette.status    import HTTP_200_OK, \
                                  HTTP_400_BAD_REQUEST, \
                                  HTTP_500_INTERNAL_SERVER_ERROR


CACHE_VALIDITY = 3600


class TelegramClient:
    tg_action_tree = {}

    tg_action_tree['/start'] = {
        'status_code': -1,
        'message': 'Ciao sono _*Plexa*_, la tua assistente virtuale 😊\n\n' + \
                   'Sono qui per aiutarti a gestire le tue richieste, che contribuiscono a migliorare ' + \
                   'l\'esperienza di Plex per tutti gli utenti\\.\n\n' + \
                   'Questa è la lista di tutte le cose che posso fare:\n\n' + \
                   '/help \\- Ti riporta a questo menù\n' + \
                   '/newRequest \\- Richiedi una nuova aggiunta a Plex\n' + \
                   '/myRequests \\- Accedi alla lista delle tue richieste'
    }
    tg_action_tree['/help'] = tg_action_tree['/start']
    tg_action_tree['/newRequest'] = {
        'status_code': 100,
        'message': 'Stai cercando un Film o una Serie TV\\?',
        'choices': [
            [{"text": 'Un Film', "callback_data": '/srcMovie'}],
            [{"text": 'Una Serie TV', "callback_data": '/srcShow'}]
        ]
    }
    tg_action_tree['/srcMovie'] = {
        'status_code':  110,
        'message':      'Vai, spara il titolo\\!'
    }
    tg_action_tree['/srcShow'] = {
        'status_code':  120,
        'message':      'Vai, spara il titolo\\!'
    }
    tg_action_tree['/myRequests'] = {
        'status_code':  200,
        'message':      'Questo è l\'elenco delle tue richieste aperte:'
    }
    tg_action_tree['requests://all'] = {
        'status_code':  200,
        'message':      'Questo è lo storico di tutte le tue richieste:'
    }
    tg_action_tree['requests://none'] = {
        'status_code':  200,
        'message':      'Non ho trovato alcuna richiesta aperta a tuo nome'
    }
    tg_action_tree['plex://found'] = {
        'status_code':  -1,
        'message':      'Ottimo, allora ti auguro una buona visione\\!'
    }
    tg_action_tree['online://found'] = {
        'status_code':  -1,
        'message':      'Perfetto, registro subito la tua richiesta'
    }
    tg_action_tree['online://not-found'] = {
        'message':      'Mi dispiace, prova a dirmi di nuovo il titolo che cerchi'
    }
    tg_action_tree['online://not-found/direct'] = {
        'message':      'Mi dispiace ma non ho trovato nulla, prova a ridirmi il titolo'
    }
    tg_action_tree['plex://results'] = {
        'message':      'Ho trovato questi titoli nella libreria di Plex, è per caso uno di loro?'
    }
    tg_action_tree['online://results'] = {
        'message':      'Ho trovato questi titoli online, dimmi quale ti interessa:'
    }
    tg_action_tree['online://seasons'] = {
        'message':      'Perfetto, queste sono le stagioni della serie, quale cercavi?'
    }

    def __init__(self):
        self.db_client       = datastore.Client(project = 'project-atlas-tools')
        self.tg_bot_token    = os.environ.get('TG_BOT_TOKEN')
        self.tg_api_base_url = 'https://api.telegram.org/bot'

    def set_user_status(self, user_id, user_status: int, message_id: int = None):
        ds_key    = self.db_client.key('tg_user_status', user_id)
        ds_entity = datastore.Entity(key = ds_key)
        ds_entity['fill_date'] = time.time()
        ds_entity['fill_data'] = { 'user_status': user_status, 'last_message_id': message_id }

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

        ds_data = ds_entity['fill_data'] if ds_entity and time.time() - ds_entity['fill_date'] < CACHE_VALIDITY else None
        return {
            'user_status':     ds_data['user_status']     if ds_data and 'user_status'     in ds_data else -1,
            'last_message_id': ds_data['last_message_id'] if ds_data and 'last_message_id' in ds_data else None
        }

    def send_message(
            self,
            callback_query_id:  int   = None,
            edit_message_id:    int   = None,
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
            response['parse_mode']   = 'MarkdownV2'
        if edit_message_id:
            response['message_id']   = edit_message_id
        if dest_chat_id:
            response['chat_id']      = dest_chat_id
        if img:
            response['photo']        = img
            response['caption']      = dest_message
        elif not callback_query_id:
            response['text']         = dest_message
        if choices:
            response['reply_markup'] = {
                'inline_keyboard': choices
            }

        tg_api_endpoint = '/answerCallbackQuery'    if callback_query_id else '/sendPhoto'   if img else \
                          '/editMessageReplyMarkup' if edit_message_id   else '/sendMessage'
        send_response   = httpx.post(
            self.tg_api_base_url + self.tg_bot_token + tg_api_endpoint,
            json    = response,
            headers = headers
        )
        logging.info('[TG] - API endpoint was called: %s', self.tg_api_base_url + tg_api_endpoint)

        result_obj = None
        try:
            result_obj = send_response.json()
        except:
            pass

        if send_response.status_code != HTTP_200_OK:
            if result_obj:
                logging.error('[TG] - Error sending message, received: %s', result_obj['description'])
            logging.error('[TG] - Error sending message while sending payload: %s', response)

            if send_response.status_code != HTTP_400_BAD_REQUEST \
            or ( result_obj and not any(error in result_obj['description'] for error in [
                'query is too old',
                'message is not modified'
            ]) ):
                raise HTTPException(
                    status_code = send_response.status_code,
                    detail      = result_obj['description'] if result_obj else 'Error while sending message'
                )

        return result_obj['result']['message_id'] if 'result' in result_obj and not callback_query_id else None

    @staticmethod
    def build_paginated_choices(
        page_key:     str,
        elements:     List[dict],
        page:         int = 1,
        page_size:    int = 5,
        extra_choice: dict = None
    ) -> List[ List[dict]]:
        result = []
        if not elements:
            return result

        if extra_choice:
            elements.append(extra_choice)
        last_page = math.ceil(len(elements) / page_size)
        prev_page  = page - 2
        next_page  = page + 2
        if prev_page < 1:
            prev_page = 1
            next_page = 5
        if next_page > last_page:
            next_page = last_page
            prev_page = last_page - 4 if last_page - 4 >= 1 else 1

        for element in elements[(page - 1) * page_size:page * page_size]:
            result.append([{'text': element['text'], 'callback_data': element['link']}])

        navigator = []
        if last_page <= 5:
            for i in range(1, last_page + 1):
                navigator.append({
                    'text': '· {} ·'.format( str(i) ) if i == page else
                              '< {}'.format( str(i) ) if i <  page else '{} >'.format( str(i) ),
                    'callback_data': page_key + '/p' + (str(i) if not page == i else '0')
                })
        else:
            for i in range(prev_page, next_page + 1):
                navigator.append({
                    'text': '· {} ·'.format( str(i) ) if i == page else
                              '< {}'.format( str(i) ) if i <  page else '{} >'.format( str(i) ),
                    'callback_data': page_key + '/p' + (str(i) if not page == i else '0')
                })
            if 1 not in range(prev_page, next_page + 1):
                navigator[0] = {
                    'text': '|< 1',
                    'callback_data': page_key + '/p' + ('1' if not page == 1 else '0')
                }
            if last_page not in range(prev_page, next_page + 1):
                navigator[-1] = {
                    'text': '{} >|'.format(str(last_page)),
                    'callback_data': page_key + '/p' + (str(last_page) if not page == last_page else '0')
                }
        if len(navigator) > 1:
            result.append(navigator)

        return result
