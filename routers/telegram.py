import os
import httpx
import logging

from   fastapi             import APIRouter, Body
from   typing              import Any
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


router = APIRouter()


@router.post(
    '',
    summary        = 'ProjectAtlasBot fulfilment'
)
async def plexa_answer( payload: Any = Body(...) ):
    logging.info(payload)

    action = payload['message']['text'].strip().lowercase()

    if action == 'aiuto':
        response = {
            "chat_id": payload['message']['from']['id'],
            "photo": "https://storage.googleapis.com/plex-api/icons/bulma_help.png",
            "caption": "Ciao sono *Plexa*, la tua assistente virtuale.",
            "parse_mode": "MarkdownV2",
            "reply_markup": {
                "keyboard": [
                    [{
                        "text": "Nuova richiesta"
                    }],
                    [{
                        "text": "Le mie richieste"
                    }],
                    [{
                        "text": "Aiuto"
                    }]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        }

    response = {
        "chat_id": 315599515,
        "text": "Fai la tua scelta",
        "parse_mode": "MarkdownV2",
        "reply_markup": {
            "keyboard": [
                [{
                    "text": "Nuova richiesta"
                }],
                [{
                    "text": "Le mie richieste"
                }],
                [{
                    "text": "Aiuto"
                }]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    }

    logging.info(response)
    httpx.post('https://api.telegram.org/bot997901652:AAHAh0qrQmP5VYcnYKCKXus86NFd76VYSok/sendMessage', data = response)
