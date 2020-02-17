import os
import httpx
import logging

from   fastapi             import APIRouter, Depends, Body, HTTPException
from   google.cloud        import bigquery
from   enum                import Enum
from   typing              import Any
from   libs.models         import env_vars_check
from   starlette.status    import HTTP_200_OK


router          = APIRouter()
tg_bot_token    = os.environ.get('TG_BOT_TOKEN')
tg_api_base_url = 'https://api.telegram.org/bot'


def verify_telegram_env_variables():
    required  = [
        'TG_BOT_TOKEN'
    ]
    suggested = []
    env_vars_check(required, suggested)


class Intent(Enum):
    WELCOME  = -1
    ACTION   =  0
    REQ_TYPE =  1


class Action(dict):
    Help       = "Aiuto"
    Start      = "/start"
    NewRequest = "Nuova richiesta"
    MyRequests = "Le mie richieste"
    SrcMovie   = "Un Film"
    SrcShow    = "Una Serie TV"


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment',
    dependencies   = [Depends(verify_telegram_env_variables)]
)
async def plexa_answer(payload: Any = Body(...), status_code = 204):
    logging.info(payload)

    headers   = { 'Content-Type': 'application/json' }
    responses = {
        Intent.WELCOME: {
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
                        "text": Action.NewRequest
                    }],
                    [{
                        "text": Action.MyRequests
                    }]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        },
        Intent.ACTION: {
            "chat_id": payload['message']['from']['id'],
            "text": "Ciao\\! Come posso aiutarti oggi\\?",
            "parse_mode": "MarkdownV2",
            "reply_markup": {
                "keyboard": [
                    [{
                        "text": Action.NewRequest
                    }],
                    [{
                        "text": Action.MyRequests
                    }]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        },
        Intent.REQ_TYPE: {
            "chat_id": payload['message']['from']['id'],
            "text": "Benissimo, cosa vorresti aggiungere\\?",
            "parse_mode": "MarkdownV2",
            "reply_markup": {
                "keyboard": [
                    [{
                        "text": Action.SrcMovie
                    }],
                    [{
                        "text": Action.SrcShow
                    }]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        }
    }

    action = payload['message']['text'].strip().lower()

    if action in [Action.Start, Action.Help.lower()]:
        tg_api_endpoint = '/sendPhoto'
        response        = responses[Intent.REQ_TYPE]
        send_response   = httpx.post(
            tg_api_base_url + tg_bot_token + tg_api_endpoint,
            json    = response,
            headers = headers
        )
        if send_response.status_code != HTTP_200_OK:
            resultObj = send_response.json()
            raise HTTPException(status_code = send_response.status_code, detail = resultObj['description'])
        return None

    if action == Action.NewRequest:
        tg_api_endpoint = '/sendMessage'
        response = responses[Intent.NEW]
        send_response = httpx.post(
            tg_api_base_url + tg_bot_token + tg_api_endpoint,
            data=response,
            headers=headers
        )
        if send_response.status_code != HTTP_200_OK:
            raise HTTPException(status_code=send_response.status_code, detail='Unable To Reply To Telegram Chat')
        return None

    bq = bigquery.Client()
    query = """
        SELECT status
        FROM project_atlas.tg_user_status
        WHERE user = %USERID%
    """
    query     = query.replace('%USERID%', payload['message']['from']['id'])
    query_job = bq.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
    results   = query_job.result()
    status    = 0 if results.num_rows == 0 else next(results)['status']
