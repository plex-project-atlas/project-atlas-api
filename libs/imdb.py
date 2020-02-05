import re
import json
import httpx
import asyncio
import urllib.parse

from   typing           import Union, List
from   starlette.status import HTTP_200_OK


class IMDBClient:
    api_url = 'https://sg.media-imdb.com/'

    def __init__(self, lang: str = 'it'):
        self.api_headers = {
            'Accept':          'application/json'
        }

    def __get_details_from_json(self, response: httpx.Response):
        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = re.search(r'^imdb\$.+?\((.+)\)$', response.text, re.IGNORECASE | re.MULTILINE)
        if not resp_obj:
            return None

        try:
            resp_obj = json.loads( resp_obj.group(1) )
        except json.JSONDecodeError:
            return None

        results = []
        for elem in resp_obj['d']:
            if 'q' not in elem:
                continue
            results.append({
                'title': elem['l'],
                'guid':  elem['id'],
                'type':  'show' if elem['q'] == 'TV series' else 'movie',
                'year':  elem['y'] if 'y' in elem else None
            })

        return {
            'query':   resp_obj['q'],
            'results': results
        }

    async def search_show_by_name(self, title: Union[ str, List[str], List[int] ]):
        async def search_worker(client: httpx.AsyncClient, query: str, headers: dict):
            api_endpoint = '/suggests/' + query[0].lower() + '/' + urllib.parse.quote(query, safe = '') +'.json'
            response = await client.get(url = IMDBClient.api_url + api_endpoint, headers = headers)
            return self.__get_details_from_json(response)

        httpx_client = httpx.AsyncClient()
        if isinstance(title, str):
            return await search_worker(httpx_client, title, self.api_headers)
        else:
            requests  = (search_worker(httpx_client, elem, self.api_headers) for elem in title)
            responses = await asyncio.gather(*requests)
            return responses
