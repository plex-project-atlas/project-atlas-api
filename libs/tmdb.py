import os
import re
import time
import httpx
import asyncio
import logging

from   fastapi          import HTTPException
from   typing           import List
from   libs.models      import Media
from   starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND


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

    def __get_show_details_from_json(self, response: httpx.Response):
        if response.status_code != HTTP_200_OK:
            message = None
            try:
                message = response.json()
                message = '. '.join(message['errors']) if 'errors' in message else ''
                logging.error('[TMDb] - Error retrieving results, received: %s', message)
            except:
                pass
            raise HTTPException(
                status_code = response.status_code,
                detail      = message if message else None
            )

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
        elif 'results'     in resp_obj:
            resp_obj = resp_obj['results']
        else:
            resp_obj = [resp_obj]
        return {
            'total_pages': total_pages,
            'results': [{
                'guid':   'tmdb://' + ('movie' if 'title' in elem else 'show') + '/' + str(elem['id']),
                'title':  (elem['title'] if elem['title']   else elem['original_title']) if 'title' in elem else
                           elem['name']  if elem['name']    else elem['original_name'],
                'type':   'movie'        if 'title' in elem else 'show',
                'year':   elem['release_date'].split('-')[0]      if 'release_date'   in elem and elem['release_date']   else
                          elem['first_air_date'].split('-')[0]    if 'first_air_date' in elem and elem['first_air_date'] else None,
                'poster': self.img_base_url + elem['poster_path'] if self.img_base_url        and elem['poster_path']    else None
            } for elem in resp_obj if 'id' in elem]
        }

    async def get_media_by_id(
        self,
        httpx_client: httpx.AsyncClient,
        media_id:     str,
        media_cache:  dict,
        media_lang:   str = 'it-IT'
    ) -> Media:
        media_type   = media_id.split('/')[-2]
        media_source = media_id.split('://')[0]

        if media_id in media_cache and time.time() - media_cache[media_id]['fill_date'] < CACHE_VALIDITY:
            logging.info('[TMDb] - Cache hit for key: %s', media_id)
            return media_cache[media_id]['fill_data']

        params = { 'language': media_lang }
        if not media_source == 'tmdb':
            api_endpoint = '/find/' + media_id.split('/')[-1]
            params['external_source'] = media_source + '_id'
        else:
            api_endpoint = '/' + ('tv' if media_type == 'show' else media_type) + '/' + media_id.split('/')[-1]
        response = await httpx_client.get(
            url     = TMDBClient.api_url + api_endpoint,
            headers = self.api_headers,
            params  = params
        )
        logging.info('[TMDb] - API endpoint was called: %s', response.request.url)
        media_search = self.__get_show_details_from_json(response)

        if not media_search['results']:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND)
        media_search = media_search['results'][0]

        media_cache[media_id] = {'fill_date': time.time(), 'fill_data': media_search}
        if not media_search['guid'] == media_id:
            media_cache[ media_search['guid'] ] = {'fill_date': time.time(), 'fill_data': media_search}
            media_search['guid'] = media_id

        return media_search

    async def search_media_by_name(
        self,
        httpx_client: httpx.AsyncClient,
        media_title:  str,
        media_type:   str,
        media_cache:  dict,
        media_lang:   str = 'it-IT',
        media_page:   int = 1
    ) -> List[Media]:
        cache_key = 'tmdb://search/' + media_type + '/' + re.sub(r'\W', '_', media_title)
        if media_page == 1 and cache_key in media_cache \
        and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
            logging.info('[TMDb] - Cache hit for key: %s', cache_key)
            return [
                media_cache[media_info]['fill_data']
                for media_info in media_cache[cache_key]['fill_data']
            ]

        api_endpoint = '/search/' + ('tv' if media_type == 'show' else media_type)
        params       = { 'language': media_lang, 'query': media_title, 'page': media_page }
        response = await httpx_client.get(
            url     = TMDBClient.api_url + api_endpoint,
            headers = self.api_headers,
            params  = params
        )
        logging.info('[TMDb] - API endpoint was called: %s', response.request.url)

        media_search = self.__get_show_details_from_json(response)
        if media_page == 1 and media_search['total_pages'] > 1:
            media_search_pages = [
                self.search_media_by_name(media_title, media_type, media_cache, media_lang, media_page)
            for media_page in range(2, media_search['total_pages'] + 1)]
            media_search_pages = await asyncio.gather(*media_search_pages)
            media_search = media_search['results'] + [ result for page in media_search_pages for result in page ]
        else:
            media_search = media_search['results']

        if media_page == 1:
            if not media_search:
                raise HTTPException(status_code = HTTP_404_NOT_FOUND)

            media_cache[cache_key] = { 'fill_date': time.time(), 'fill_data': [] }
            for media_info in media_search:
                media_cache[cache_key]['fill_data'].append(media_info['guid'])
                media_cache[ media_info['guid'] ] = { 'fill_date': time.time(), 'fill_data': media_info }

        return media_search
