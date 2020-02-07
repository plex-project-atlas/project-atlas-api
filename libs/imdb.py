import re
import json
import httpx
import asyncio
import logging
import urllib.parse

from   typing           import List
from   starlette.status import HTTP_200_OK


class IMDBClient:
    api_url = 'https://sg.media-imdb.com'

    def __init__(self, lang: str = 'it'):
        self.api_headers = {
            'Accept':          'application/json'
        }

    def __get_details_from_json(self, query, query_type: str, response: httpx.Response):
        if response.status_code != HTTP_200_OK:
            return None

        response.encoding = 'UTF-8'
        resp_obj = re.search(r'^imdb\$.+?\((.+)\)$', response.text, re.IGNORECASE | re.MULTILINE)
        if not resp_obj:
            return None

        try:
            resp_obj = json.loads( resp_obj.group(1) )
        except json.JSONDecodeError:
            return None

        results = []
        if 'd' in resp_obj:
            for elem in resp_obj['d']:
                if 'q' not in elem:
                    continue
                results.append({
                    'guid':   'imdb:' + elem['id'],
                    'title':  elem['l'],
                    'type':   'show'       if elem['q'] == 'TV series' else 'movie',
                    'year':   elem['y']    if 'y' in elem              else None,
                    'poster': elem['i'][0] if 'i' in elem              else None
                })

        return {
            'query':   query,
            'results': [item for item in results if item['type'] == query_type]
        }

    async def search_media_by_name(self, titles: List[str], media_type: str):
        async def search_worker(client: httpx.AsyncClient, query, query_type: str, headers: dict):
            api_endpoint = '/suggests/' + query[0].lower() + '/' + urllib.parse.quote(query, safe = '') +'.json'
            logging.info('IMDBClient - Calling API endpoint: %s', IMDBClient.api_url + api_endpoint)
            response = await client.get(url = IMDBClient.api_url + api_endpoint, headers = headers)
            return self.__get_details_from_json(query, query_type, response)

        httpx_client = httpx.AsyncClient()
        requests     = (search_worker(httpx_client, elem.strip(), media_type, self.api_headers) for elem in titles)
        responses    = await asyncio.gather(*requests)
        return responses
