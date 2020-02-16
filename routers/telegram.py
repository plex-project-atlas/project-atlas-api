import os
import asyncio
import logging

from   fastapi             import APIRouter, Body
from   typing              import Any
from   starlette.status    import HTTP_501_NOT_IMPLEMENTED, \
                                  HTTP_503_SERVICE_UNAVAILABLE, \
                                  HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


router = APIRouter()


@router.post(
    '/',
    summary        = 'ProjectAtlasBot fulfilment'
)
async def plexa_answer(body: Any = Body(...)):
    logging.info(body)
    return body