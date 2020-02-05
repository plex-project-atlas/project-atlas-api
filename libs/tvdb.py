import os
import httpx
import asyncio

from   typing           import Optional, Union, List
from   starlette.status import HTTP_200_OK


class TVDBClient:
    # Ref: https://api.thetvdb.com/swagger (v3.0.0)
    api_url = 'https://api.thetvdb.com'

    def __init__(self, lang: str = 'it'):
        self.usr_name    = os.environ.get('TVDB_USR_NAME')
        self.usr_key     = os.environ.get('TVDB_USR_KEY')
        self.api_key     = os.environ.get('TVDB_API_KEY')
        self.api_token   = self.__get_jwt_token()
        self.api_headers = {
            'Accept':          'application/vnd.thetvdb.v3.0.0',
            'Content-Type':    'application/json',
            'Authorization':   'Bearer ' + self.api_token if self.api_token else '',
            'Accept-Language': lang
        }

    def __get_show_details_from_json(self, response: httpx.Response):
        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = response.json()
        resp_obj = resp_obj['data'] if isinstance(resp_obj['data'], list) else [ resp_obj['data'] ]
        return [{
            'guid':    elem['id'],
            'imdb_id': elem['imdbId'] if 'imdbId' in elem else None,
            'title':   elem['seriesName'],
            'year':    elem['firstAired'].split('-')[0] if elem['firstAired'] else None
        } for elem in resp_obj]

    def __get_jwt_token(self) -> Optional[str]:
        api_endpoint = '/login'
        headers = {
            'Accept':       'application/json',
            'Content-Type': 'application/json'
        }
        payload = {
            'username': self.usr_name,
            'userkey':  self.usr_key,
            'apikey':   self.api_key
        }
        response = httpx.post(url = TVDBClient.api_url + api_endpoint, headers = headers, json = payload)

        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = response.json()
        return resp_obj['token']

    async def get_show_by_id(self, tvdb_id: Union[ str, int, List[str] ]):
        async def search_worker(client: httpx.AsyncClient, query_id: str, headers: dict):
            api_endpoint = '/series/' + query_id
            response = await client.get(url = TVDBClient.api_url + api_endpoint, headers = headers)
            return self.__get_show_details_from_json(response)

        httpx_client = httpx.AsyncClient()
        if isinstance(tvdb_id, str):
            return await search_worker(httpx_client, tvdb_id, self.api_headers)
        elif isinstance(tvdb_id, int):
            return await search_worker(httpx_client, str(tvdb_id), self.api_headers)
        else:
            requests  = (search_worker(httpx_client, str(elem), self.api_headers) for elem in tvdb_id)
            responses = await asyncio.gather(*requests)
            return dict( zip(tvdb_id, responses) )

    async def search_show_by_name(self, title: Union[ str, List[str], List[int] ]):
        async def search_worker(client: httpx.AsyncClient, query: str, headers: dict):
            api_endpoint = '/search/series'
            params = {
                'name': query
            }
            response = await client.get(url = TVDBClient.api_url + api_endpoint, headers = headers, params = params)
            return self.__get_show_details_from_json(response)

        httpx_client = httpx.AsyncClient()
        if isinstance(title, str):
            return await search_worker(httpx_client, title, self.api_headers)
        else:
            requests  = (search_worker(httpx_client, elem, self.api_headers) for elem in title)
            responses = await asyncio.gather(*requests)
            return dict( zip(title, responses) )
