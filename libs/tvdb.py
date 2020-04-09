import os
import sys
import httpx
import asyncio
import logging

from   typing           import Optional, List
from   starlette.status import HTTP_200_OK


class TVDBClient:
    # Ref: https://api.thetvdb.com/swagger (v3.0.0)
    api_url = 'https://api.thetvdb.com'

    def __init__(self):
        self.usr_name    = os.environ.get('TVDB_USR_NAME')
        self.usr_key     = os.environ.get('TVDB_USR_KEY')
        self.api_key     = os.environ.get('TVDB_API_KEY')
        self.api_token   = self.__get_jwt_token()
        self.api_headers = {
            'Accept':          'application/vnd.thetvdb.v3.0.0',
            'Content-Type':    'application/json',
            'Authorization':   'Bearer ' + self.api_token if self.api_token else ''
        }

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
        try:
            response = httpx.post(
                url     = TVDBClient.api_url + api_endpoint,
                headers = headers,
                json    = payload,
                timeout = None
            )
        except:
            error_details = sys.exc_info()
            logging.error('[TVDb] - Error while retrieving JWT token: %s', error_details[0])
            return None

        if response.status_code != HTTP_200_OK:
            logging.error('[TVDb] - Error while retrieving JWT token: APIs returned error %s', response.status_code)
            return None

        resp_obj = response.json()
        return resp_obj['token']

    @staticmethod
    def __get_show_details_from_json(query: str, response: httpx.Response):
        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = response.json()
        resp_obj = resp_obj['data'] if isinstance(resp_obj['data'], list) else [ resp_obj['data'] ]
        return {
            'query': query,
            'results': [{
                'guid':   'tvdb://' + str(elem['id']),
                'title':   elem['seriesName'],
                'type':   'show' if 'seriesName' in elem else 'movie',
                'year':    elem['firstAired'].split('-')[0]       if elem['firstAired'] else None,
                'poster': 'https://thetvdb.com' + elem['poster'] if elem['poster']     else None
            } for elem in resp_obj]
        }

    async def get_media_by_id(self, media_ids: List[dict], lang: str = 'it'):
        async def get_worker(client: httpx.AsyncClient, media_id: str, media_type: str,
                             media_source: str, media_lang: str, headers: dict):
            params = None
            headers['Accept-Language'] = media_lang
            if media_source:
                api_endpoint = '/search/series'
                params = {media_source + 'Id': media_id}
            else:
                api_endpoint = '/' + ('movies' if media_type == 'movie' else 'series') + '/' + media_id
            logging.info('[TVDb] - Calling API endpoint: %s', TVDBClient.api_url + api_endpoint)
            response = await client.get(url = TVDBClient.api_url + api_endpoint, headers = headers, params = params)
            return self.__get_show_details_from_json(media_id, response)

        httpx_client = httpx.AsyncClient()
        requests     = [get_worker(
            httpx_client,
            media_id['id'],
            media_id['type'],
            media_id['source'] if 'source' in media_id else None,
            lang,
            self.api_headers
        ) for media_id in media_ids]
        responses    = await asyncio.gather(*requests)
        return responses

    async def search_media_by_name(self, media_titles: List[dict], lang: str = 'it'):
        async def search_worker(client: httpx.AsyncClient, media_title, media_type, media_lang: str, headers: dict):
            api_endpoint = '/search/series'
            params = { 'name': media_title }
            headers['Accept-Language'] = lang
            logging.info('[TVDb] - Calling API endpoint: %s', TVDBClient.api_url + api_endpoint)
            response = await client.get(url = TVDBClient.api_url + api_endpoint, headers = headers, params = params)
            return self.__get_show_details_from_json(media_title, response)

        httpx_client = httpx.AsyncClient()
        requests = [search_worker(
            httpx_client,
            media_title['title'],
            media_title['type'],
            lang,
            self.api_headers
        ) for media_title in media_titles]
        responses = await asyncio.gather(*requests)
        return responses
