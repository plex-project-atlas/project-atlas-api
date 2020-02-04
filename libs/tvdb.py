import os
import httpx
import asyncio

from   typing           import Union, List
from   starlette.status import HTTP_200_OK


class TVDBClient:
    # Ref: https://api.thetvdb.com/swagger (v3.0.0)
    api_url = 'https://api.thetvdb.com'

    def __init__(self, lang: str = 'it'):
        self.usr_name    = os.environ.get('TVDB_USR_NAME')
        self.usr_key     = os.environ.get('TVDB_USR_KEY')
        self.api_key     = os.environ.get('TVDB_API_KEY')
        self.api_headers = {
            'Accept':          'application/vnd.thetvdb.v3.0.0',
            'Content-Type':    'application/json',
            'Authorization':   'Bearer ' + self.get_jwt_token(),
            'Accept-Language': lang
        }

    def get_jwt_token(self):
        headers = {
            'Accept':       'application/json',
            'Content-Type': 'application/json'
        }
        payload = {
            'username': self.usr_name,
            'userkey':  self.usr_key,
            'apikey':   self.api_key
        }
        response = httpx.post(url = TVDBClient.api_url + '/login', headers = headers, json = payload)

        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = response.json()
        return resp_obj['token']

    async def search_show_by_name(self, title: Union[ str, List[str] ]):
        async def search_worker(client: httpx.AsyncClient, query: str, headers: dict):
            api_endpoint = '/search/series'
            params = {
                'name': query
            }
            response = await client.get(url = TVDBClient.api_url + api_endpoint, headers = headers, params = params)

            if response.status_code != HTTP_200_OK:
                return None

            resp_obj = response.json()
            return [{
                'guid': elem['id'],
                'title': elem['seriesName'],
                'year': elem['firstAired'].split('-')[0] if elem['firstAired'] else None
            } for elem in resp_obj['data']]

        if isinstance(title, str):
            with httpx.AsyncClient() as httpx_client:
                return await search_worker(httpx_client, title, self.api_headers)
        elif isinstance(title, List):
            with httpx.AsyncClient() as httpx_client:
                requests = (search_worker(httpx_client, elem, self.api_headers) for elem in title)
            return await asyncio.gather(*requests)
        return None
