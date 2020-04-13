import os
import re
import time
import httpx
import asyncio
import logging

from   typing           import List
from   starlette.status import HTTP_200_OK

CACHE_VALIDITY = 86400  # 1 day


class TMDBClient:
    # Ref: https://developers.themoviedb.org/3 (v3)
    api_url = 'https://api.themoviedb.org/3'

    def __init__(self):
        self.api_token    = os.environ.get('TMDB_API_TOKEN')
        self.api_headers  = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_token if self.api_token else ''
        }
        self.img_base_url = self.__get_api_conf_params()

    def __get_api_conf_params(self):
        api_endpoint = '/configuration'
        response = httpx.get(url = TMDBClient.api_url + api_endpoint, headers = self.api_headers)

        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = response.json()
        return resp_obj['images']['secure_base_url'] + resp_obj['images']['poster_sizes'][-1]

    def __get_show_details_from_json(self, query: str, response: httpx.Response):
        if response.status_code != HTTP_200_OK:
            return None

        try:
            resp_obj = response.json()
        except:
            logging.error('[TMDb] - Error while parsing results: %s', response.request.url)
            return None

        total_pages = resp_obj['total_pages'] if 'total_pages' in resp_obj else 1
        if 'movie_results' in resp_obj and resp_obj['movie_results']:
            resp_obj = resp_obj['movie_results']
        elif 'tv_results'  in resp_obj and resp_obj['tv_results']:
            resp_obj = resp_obj['tv_results']
        elif 'results'     in resp_obj and resp_obj['results']:
            resp_obj = resp_obj['results']
        else:
            resp_obj = [resp_obj]
        return {
            'query': query,
            'total_pages': total_pages,
            'results': [{
                'guid':   'tmdb://' + ('movie' if 'title' in elem else 'show') + '/' + str(elem['id']),
                'title':  (elem['title'] if elem['title']   else elem['original_title']) if 'title' in elem else
                           elem['name']  if elem['name']    else elem['original_name'],
                'type':   'movie'        if 'title' in elem else 'show',
                'year':   elem['release_date'].split('-')[0]      if 'release_date'   in elem and elem['release_date']   else
                          elem['first_air_date'].split('-')[0]    if 'first_air_date' in elem and elem['first_air_date'] else None,
                'poster': self.img_base_url + elem['poster_path'] if self.img_base_url        and elem['poster_path']    else None
            } for elem in resp_obj]
        }

    async def get_media_by_id(self, media_ids: List[str], media_cache: dict, media_lang: str = 'it-IT'):
        async def get_worker(client: httpx.AsyncClient, media_id):
            media_type   = media_id.split('/')[-2]
            media_source = media_id.split('://')[0]

            if media_id in media_cache and time.time() - media_cache[media_id]['fill_date'] < CACHE_VALIDITY:
                logging.info('[TMDb] - Cache hit for key: %s', media_id.split('://')[1])
                return media_cache[media_id]['fill_data']

            params = { 'language': media_lang }
            if not media_source == 'tmdb':
                api_endpoint = '/find/' + media_id.split('/')[-1]
                params['external_source'] = media_source + '_id'
            else:
                api_endpoint = '/' + ('tv' if media_type == 'show' else media_type) + '/' + media_id.split('/')[-1]
            logging.info('[TMDb] - Calling API endpoint: %s', TMDBClient.api_url + api_endpoint)
            response = await client.get(
                url  = TMDBClient.api_url + api_endpoint, headers = self.api_headers, params = params
            )
            media_search = self.__get_show_details_from_json(media_id, response)
            media_cache[media_id] = { 'fill_date': time.time(), 'fill_data': media_search }

            return media_search

        httpx_client = httpx.AsyncClient()
        requests     = [get_worker(httpx_client, media_id) for media_id in media_ids]
        responses    = await asyncio.gather(*requests)
        return responses

    async def search_media_by_name(self, media_titles: List[dict], media_cache: dict, media_lang: str = 'it-IT'):
        async def search_worker(client: httpx.AsyncClient, media_title, media_type: str, page: int = 1):
            cache_key = 'tmdb://search/' + re.sub(r'\W', '_', media_title)
            if cache_key in media_cache and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
                logging.info('[TMDb] - Cache hit for key: %s', cache_key)
                return {
                    'query': media_title,
                    'results': [
                        media_cache[media_info]['fill_data']
                        for media_info in media_cache[cache_key]['fill_data']
                    ]
                }

            api_endpoint = '/search/' + ('tv' if media_type == 'show' else media_type)
            params       = { 'language': media_lang, 'query': media_title, 'page': page }
            logging.info('[TMDb] - Calling API endpoint: %s', TMDBClient.api_url + api_endpoint)
            response = await client.get(
                url  = TMDBClient.api_url + api_endpoint, headers = self.api_headers, params = params
            )
            media_search = self.__get_show_details_from_json(cache_key, response)
            if page == 1 and media_search['total_pages'] > 1:
                media_search_pages = [search_worker(
                    client, media_title, media_type, media_page)
                for media_page in range(2, media_search['total_pages'] + 1)]
                media_search_pages = await asyncio.gather(*media_search_pages)
                media_search_pages = [media_search] + media_search_pages
                media_search = {
                    'query':   media_search['query'],
                    'results': [ result for media_search_page in media_search_pages for result in media_search_page['results'] ]
                }

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
