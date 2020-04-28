import os
import re
import sys
import time
import httpx
import asyncio
import logging

from   fastapi          import HTTPException
from   typing           import Optional, List
from   starlette.status import HTTP_200_OK


CACHE_VALIDITY = 86400  # 1 day


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
            message = None
            try:
                message = response.json()
                message = message['Error'] if 'Error' in message else ''
                logging.error('[TVDb] - Error retrieving results, received: %s', message)
            except:
                pass
            raise HTTPException(
                status_code = response.status_code,
                detail      = message if message else response.request.url
            )

        try:
            resp_obj = response.json()
        except:
            logging.error('[TVDb] - Error while parsing results: %s', response.request.url)
            return None

        num_pages = resp_obj['links']['last'] if 'links' in resp_obj and 'last' in resp_obj['links'] else None
        resp_obj  = resp_obj['data'] if isinstance(resp_obj['data'], list) else [ resp_obj['data'] ]
        if 'episodes' not in response.request.url.path:
            return {
                'query': query,
                'results': [{
                    'guid':   'tvdb://' + ('show' if 'seriesName' in elem else 'movie') + '/' + str(elem['id']),
                    'title':   elem['seriesName'],
                    'type':   'show' if 'seriesName' in elem else 'movie',
                    'year':    elem['firstAired'].split('-')[0]      if elem['firstAired'] else None,
                    'poster': 'https://thetvdb.com' + elem['poster'] if elem['poster']     else None
                } for elem in resp_obj]
            }
        else:
            return {
                'pages': num_pages,
                'episodes': [{
                    'title':              elem['episodeName'],
                    'translated':         True if elem['overview']   else False,
                    'season_number':      elem['airedSeason']        if 'airedSeason' in elem else elem['dvdSeason'],
                    'episode_number':     elem['airedEpisodeNumber'] if 'airedSeason' in elem else elem['dvdEpisodeNumber'],
                    'episode_abs_number': elem['absoluteNumber']
                } for elem in resp_obj]
            }

    async def __get_show_episodes(self, client: httpx.AsyncClient, media_id: str, media_page: int = 1):
        api_endpoint = '/series/{id}/episodes/query'.format(id = media_id)
        params       = { 'page': media_page }
        response     = await client.get(
            url = TVDBClient.api_url + api_endpoint, headers = self.api_headers, params = params
        )
        logging.info('[TVDb] - API endpoint was called: %s', response.request.url)
        media_search = self.__get_show_details_from_json(media_id, response)
        if media_page == 1 and media_search['pages'] > 1:
            media_search_pages = [self.__get_show_episodes(
                client, media_id, media_page)
            for media_page in range(2, media_search['pages'] + 1)]
            media_search_pages = await asyncio.gather(*media_search_pages)
            media_search_pages = [ media_search['episodes'] ] + media_search_pages
            media_search = [ episode for search_page in media_search_pages for episode in search_page ]
        else:
            media_search = media_search['episodes']

        if media_page > 1:
            return media_search

        result = []
        for episode in media_search:
            while len(result) < episode['season_number'] + 1:
                result.append({ 'episodes': [] })
            while len(result[ episode['season_number'] ]['episodes']) < episode['episode_number'] + 1:
                result[ episode['season_number'] ]['episodes'].append(None)
            result[ episode['season_number'] ]['episodes'][ episode['episode_number'] ] = {
                'title':      episode['title'],
                'abs_number': episode['episode_abs_number'],
                'translated': episode['translated']
            }

        return result

    async def get_media_by_id(
            self, media_ids: List[str], media_cache: dict, media_lang: str = 'it', info_only = True):
        async def get_worker(client: httpx.AsyncClient, media_id):
            cache_key    = media_id if info_only else media_id + '/episodes'
            media_type   = media_id.split('/')[-2]
            media_source = media_id.split('://')[0]

            if cache_key in media_cache and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
                logging.info('[TVDb] - Cache hit for key: %s', media_id.split('://')[1])
                return {
                    'query': media_id,
                    'results': [
                        media_cache[media_info]['fill_data']
                        for media_info in media_cache[cache_key]['fill_data']
                    ]
                }

            params = None
            self.api_headers['Accept-Language'] = media_lang
            if not media_source == 'tvdb':
                api_endpoint = '/search/series'
                params = { media_source + 'Id': media_id.split('/')[-1] }
            else:
                api_endpoint = '/' + ('movies' if media_type == 'movie' else 'series') + '/' + media_id.split('/')[-1]
            response = await client.get(
                url = TVDBClient.api_url + api_endpoint, headers = self.api_headers, params = params
            )
            logging.info('[TVDb] - API endpoint was called: %s', response.request.url)
            media_search = self.__get_show_details_from_json(media_id, response)
            if not info_only:
                media_search['results'][0]['seasons'] = await self.__get_show_episodes(client, media_id.split('/')[-1])
            media_cache[cache_key] = { 'fill_date': time.time(), 'fill_data': media_search }

            return media_search

        httpx_client = httpx.AsyncClient()
        requests     = [get_worker(httpx_client, media_id) for media_id in media_ids]
        responses    = await asyncio.gather(*requests)
        return responses

    async def search_media_by_name(self, media_titles: List[dict], media_cache: dict, media_lang: str = 'it'):
        async def search_worker(client: httpx.AsyncClient, media_title, media_type: str):
            cache_key = 'tvdb://search/' + media_type + '/' + re.sub(r'\W', '_', media_title)
            if cache_key in media_cache and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
                logging.info('[TVDb] - Cache hit for key: %s', cache_key)
                return {
                    'query':   media_title,
                    'results': [
                        media_cache[media_info]['fill_data']
                        for media_info in media_cache[cache_key]['fill_data']
                    ]
                }

            api_endpoint = '/search' + ('/series' if media_type == 'show' else '')
            params       = { 'name': media_title }
            self.api_headers['Accept-Language'] = media_lang
            response = await client.get(
                url  = TVDBClient.api_url + api_endpoint, headers = self.api_headers, params = params
            )
            logging.info('[TMDb] - API endpoint was called: %s', response.request.url)
            media_search = self.__get_show_details_from_json(cache_key, response)

            media_cache[cache_key] = { 'fill_date': time.time(), 'fill_data': [] }
            for media_info in media_search['results']:
                media_cache[cache_key]['fill_data'].append(media_info['guid'])
                media_cache[ media_info['guid'] ] = { 'fill_date': time.time(), 'fill_data': media_info }

            return media_search

        httpx_client = httpx.AsyncClient()
        requests     = [search_worker(
            httpx_client,
            media_title['title'],
            media_title['type']
        ) for media_title in media_titles]
        responses    = await asyncio.gather(*requests)

        return responses
