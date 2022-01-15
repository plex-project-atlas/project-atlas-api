import os
import re
import time
import httpx
import asyncio
import logging

from   fastapi          import HTTPException
from   typing           import Optional, List, Dict
from   langdetect       import detect, lang_detect_exception, DetectorFactory
from   libs.models      import Media
from   libs.commons     import async_ext_api_call
from   starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR


CACHE_VALIDITY = 86400  # 1 day


class TVDBClient:
    def __init__(self, http_client: httpx.AsyncClient):
        # Ref: https://app.swaggerhub.com/apis-docs/thetvdb/tvdb-api_v_4/4.1.0 (v4.1.0)
        self.api_url     = 'https://api4.thetvdb.com/v4'
        self.usr_pin     = os.environ.get('TVDB_USR_PIN')
        self.api_key     = os.environ.get('TVDB_API_KEY')
        self.api_headers = {
            'Accept':          'application/json',
            'Content-Type':    'application/json',
        }
        self.api_token   = None
        self.http_client = http_client

    async def do_authenticate(self):
        api_endpoint = '/login'
        payload = {
            'pin':    self.usr_pin,
            'apikey': self.api_key
        }
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = self.api_url + api_endpoint,
            use_post    = True,
            headers     = self.api_headers,
            json        = payload,
            timeout     = 300
        )
        self.api_token = response['data']['token']
        self.api_headers['Authorization'] = 'Bearer ' + self.api_token if self.api_token else ''

    @staticmethod
    def __get_show_details_from_json(response: Dict):
        def detect_language(text: str, lang: str = 'it'):
            if not text:
                return False
            try:
                return detect(text) == lang
            except lang_detect_exception.LangDetectException:
                return False
                pass

        num_pages = response['links']['last'] if 'links' in response and 'last' in response['links'] else None
        resp_obj  = response['data'] if isinstance(response['data'], list) else [ response['data'] ]
        if 'episodes' not in response.request.url.path:
            return {
                'results': [{
                    'guid':   'tvdb://' + ('show' if 'seriesName' in elem else 'movie') + '/' + str(elem['id']),
                    'title':   elem['seriesName'],
                    'type':   'show' if 'seriesName' in elem else 'movie',
                    'year':    elem['firstAired'].split('-')[0]      if elem['firstAired'] else None,
                    'poster': 'https://thetvdb.com' + elem['poster'] if elem['poster']     else None
                } for elem in resp_obj]
            }
        else:
            DetectorFactory.seed = 0
            return {
                'pages': num_pages,
                'episodes': [{
                    'title':              elem['episodeName'],
                    'translated':         True if elem['overview']   else detect_language(elem['episodeName']),
                    'season_number':      elem['airedSeason']        if 'airedSeason' in elem else elem['dvdSeason'],
                    'episode_number':     elem['airedEpisodeNumber'] if 'airedSeason' in elem else elem['dvdEpisodeNumber'],
                    'episode_abs_number': elem['absoluteNumber'],
                    'episode_air_date':   elem['firstAired']
                } for elem in resp_obj]
            }

    async def __get_show_episodes(self, httpx_client: httpx.AsyncClient, media_id: str, media_page: int = 1):
        api_endpoint = '/series/{id}/episodes/query'.format(id = media_id)
        params       = { 'page': media_page }
        response = await httpx_client.get(
            url     = TVDBClient.api_url + api_endpoint,
            headers = self.api_headers,
            params  = params
        )
        logging.info('[TVDb] - API endpoint was called: %s', response.request.url)
        media_search = self.__get_show_details_from_json(response)
        if media_page == 1 and media_search['pages'] > 1:
            media_search_pages = [
                self.__get_show_episodes(httpx_client, media_id, media_page)
                for media_page in range(2, media_search['pages'] + 1)
            ]
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
                'title':          episode['title'],
                'abs_number':     episode['episode_abs_number'],
                'first_air_date': episode['episode_air_date'],
                'translated':     episode['translated']
            }

        return result

    async def get_media_by_id(
        self,
        httpx_client: httpx.AsyncClient,
        media_id:     str,
        media_cache:  dict,
        media_lang:   str  = 'it',
        info_only:    bool = True
    ) -> Media:
        cache_key    = media_id if info_only else media_id + '/episodes'
        media_type   = media_id.split('/')[-2]
        media_source = media_id.split('://')[0]

        if cache_key in media_cache and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
            logging.info('[TVDb] - Cache hit for key: %s', cache_key)
            return media_cache[cache_key]['fill_data']
        elif info_only and media_id + '/episodes' in media_cache and \
        time.time() - media_cache[media_id + '/episodes']['fill_date'] < CACHE_VALIDITY:
            logging.info('[TVDb] - Cache hit for key: %s', cache_key)
            return media_cache[cache_key]['fill_data']

        params = None
        self.api_headers['Accept-Language'] = media_lang
        if not media_source == 'tvdb':
            api_endpoint = '/search/series'
            params = { media_source + 'Id': media_id.split('/')[-1] }
        else:
            api_endpoint = '/' + ('movies' if media_type == 'movie' else 'series') + '/' + media_id.split('/')[-1]
        response = await async_ext_api_call(
            http_client = httpx_client,
            url         = TVDBClient.api_url + api_endpoint,
            headers     = self.api_headers,
            params      = params
        )
        media_search = self.__get_show_details_from_json(response)

        if not media_search['results']:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND)
        media_search = media_search['results'][0]
        if not info_only:
            media_search['seasons'] = await self.__get_show_episodes(httpx_client, media_id.split('/')[-1])

        media_cache[cache_key] = { 'fill_date': time.time(), 'fill_data': media_search }
        if not media_search['guid'] in cache_key:
            media_cache[ media_search['guid'] ] = {'fill_date': time.time(), 'fill_data': media_search}
            media_search['guid'] = media_id

        return media_search

    async def search_media_by_name(
        self,
        httpx_client: httpx.AsyncClient,
        media_title:  str,
        media_type:   str,
        media_cache:  dict,
        media_year:   int = None,
        media_lang:   str = 'it'
    ) -> List[Media]:
        # Serving from cache
        cache_key = f'tvdb://search/{media_type}/' + re.sub(r'\W', '_', media_title)
        if cache_key in media_cache and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
            logging.info('[TVDb] - Cache hit for key: %s', cache_key)
            return [
                media_cache[media_info]['fill_data']
                for media_info in media_cache[cache_key]['fill_data']
            ]
        # -----------------

        api_endpoint = '/search'
        params       = {
            'query': media_title,
            'type':  media_type,
        }
        if media_year:
            params['year'] = media_year
        self.api_headers['Accept-Language'] = media_lang
        response = await async_ext_api_call(
            http_client = httpx_client,
            url         = TVDBClient.api_url + api_endpoint,
            headers     = self.api_headers,
            params      = params
        )
        media_search = self.__get_show_details_from_json(response)
        if not media_search['results']:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND)

        # Filling the cache
        media_cache[cache_key] = { 'fill_date': time.time(), 'fill_data': [] }
        for media_info in media_search['results']:
            media_cache[cache_key]['fill_data'].append(media_info['guid'])
            media_cache[ media_info['guid'] ] = { 'fill_date': time.time(), 'fill_data': media_info }
        # -----------------

        return media_search['results']
