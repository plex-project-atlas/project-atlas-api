import sys
import httpx
import random
import time
import logging
import urllib.parse

from pydantic         import HttpUrl
from typing           import Callable
from json             import JSONDecodeError
from fastapi          import HTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

async def async_ext_api_call(
    http_client: httpx.AsyncClient,
    url:         HttpUrl,
    method:      Callable[..., httpx.Response],
    caller:      str,
    max_retries: int = 6,
    **kwargs
):
    tries = max_retries + 1
    response = { }

    while tries:
        try:
            if len(kwargs.get('params', [ ])) > 0:
                url_encoded=f'{url}?{"&".join(["=".join([key, urllib.parse.quote(value.encode("utf-8"))]) for key, value in kwargs["params"].items()])}'
                logging.error(f'[{caller}] - An external API endpoint is beeing called: {url_encoded}')
            else:
                logging.error(f'[{caller}] - An external API endpoint is beeing called: {url}')

            api_call = await method(http_client, url=url, **kwargs)
            api_call.raise_for_status()
            response = api_call.json()

            break
        except (httpx.DecodingError, JSONDecodeError):
            logging.error(f'[{caller}] - Error while parsing external API results: {url}')
            exception = HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR)
        except httpx.RequestError:
            error_details = sys.exc_info()
            logging.error(
                f'[{caller}] - Error while calling external API endpoint ({max_retries - tries + 2}/{max_retries}): {error_details[0]}'
            )
            exception = HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR)
        except httpx.HTTPStatusError as e:
            message = response['Error'] if 'Error' in response else None
            logging.error(
                f'[{caller}] - Error was returned by external API with code ({max_retries - tries + 2}/{max_retries}): {e.response.status_code}'
            )
            exception = HTTPException(status_code = e.response.status_code, detail = message)

        tries -= 1

        if tries > 0:
            sleep_time = random.randint(1, 1000)
            time.sleep((2 ** (max_retries - tries - 1) * 1000 + sleep_time) / 1000)

    if tries == 0:
        raise exception
        
    return response