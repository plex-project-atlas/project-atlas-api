import sys
import time
import httpx
import random
import logging
import tldextract

from   json             import JSONDecodeError
from   fastapi          import HTTPException
from   starlette.status import HTTP_500_INTERNAL_SERVER_ERROR


async def async_ext_api_call(
        http_client: httpx.AsyncClient,
        url:         str,
        use_post:    bool = False,
        parse_json:  bool = True,
        caller:      str  = None,
        max_retries: int  = 6,
        **kwargs
):
    logging.getLogger('tldextract.cache').disabled = True
    logging.getLogger('tldextract').disabled       = True

    api_client = http_client.get if not use_post else http_client.post
    api_domain = tldextract.extract(url).domain
    info_endpoint = caller if caller else 'TBD'
    if api_domain == 'thetvdb':
        info_endpoint = 'TVDb'
    elif api_domain == 'themoviedb':
        info_endpoint = 'TMDb'

    retry    = True
    num_try  = 0
    response = {}
    while retry:
        if num_try < max_retries:
            num_try = num_try + 1
        retry = num_try != max_retries
        logging.info(f'[{info_endpoint}] - An external API endpoint is beeing called: {url}')
        try:
            api_call = await api_client(url = url, **kwargs)
            api_call.raise_for_status()
            response = api_call.json() if parse_json else api_call
            retry    = False
        except (httpx.DecodingError, JSONDecodeError):
            logging.error(f'[{info_endpoint}] - Error while parsing external API results: {url}')
            if not retry:
                raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR)
        except httpx.RequestError:
            error_details = sys.exc_info()
            logging.error(
                f'[{info_endpoint}] - Error while calling external API endpoint \
                ({num_try}/{max_retries}): {error_details[0]}'
            )
            if not retry:
                raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR)
        except httpx.HTTPStatusError as e:
            message = response['Error'] if 'Error' in response else None
            logging.error(
                f'[{info_endpoint}] - Error was returned by external API with code \
                ({num_try}/{max_retries}): {e.response.status_code}'
            )
            if message:
                logging.error(f'[{info_endpoint}] - Error was returned by external API with message: {message}')
            if not retry:
                raise HTTPException(status_code = e.response.status_code, detail = message)
        if retry:
            random_sleep_time = random.randint(1, 1000)  # randomly sleep for additional 1ms to 1s
            logging.debug(f'[{info_endpoint}] - An error occurred, triggering exponential backoff')
            logging.debug(f'[{info_endpoint}] - Sleeping for {2 ** (num_try - 1) * 1000} + {random_sleep_time} ms')
            time.sleep( (2 ** (num_try - 1) * 1000 + random_sleep_time) / 1000 )

    logging.getLogger('tldextract').disabled       = False
    logging.getLogger('tldextract.cache').disabled = False

    return response
