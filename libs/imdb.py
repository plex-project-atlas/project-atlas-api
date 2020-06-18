import re
import json
import time
import httpx
import asyncio
import logging
import urllib.parse

from   fastapi          import Request, HTTPException
from   typing           import List
from   libs.models      import Media
from   google.cloud     import bigquery
from   starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND


CACHE_VALIDITY = 86400  # 1 day


class IMDBClient:
    api_url = 'https://sg.media-imdb.com'

    def __init__(self, lang: str = 'it'):
        self.api_headers = {
            'Accept': 'application/json'
        }
        self.bq_client = bigquery.Client()

    @staticmethod
    def __get_details_from_json(media_type: str, response: httpx.Response):
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
                    'guid':   'imdb://' + ('show/' if elem['q'] == 'TV series' else 'movie/') + elem['id'],
                    'title':  elem['l'],
                    'type':   'show'       if elem['q'] == 'TV series' else 'movie',
                    'year':   elem['y']    if 'y' in elem              else None,
                    'poster': elem['i'][0] if 'i' in elem              else None
                })

        return {'results': [item for item in results if item['type'] == media_type] if media_type else results}

    async def search_media_by_name(
        self,
        request:      Request,
        media_title:  str,
        media_type:   str
    ) -> List[Media]:
        cache_key = 'imdb://search/' + media_type + '/' + re.sub(r'\W', '_', media_title)
        if cache_key in request.state.cache and time.time() - request.state.cache[cache_key]['fill_date'] < CACHE_VALIDITY:
            logging.info('[TMDb] - Cache hit for key: %s', cache_key)
            return [
                request.state.cache[media_info]['fill_data']
                for media_info in request.state.cache[cache_key]['fill_data']
            ]

        api_endpoint = '/suggests/' + media_title[0].lower() + '/' + urllib.parse.quote(media_title, safe = '') + '.json'
        response = await request.state.httpx.get(
            url     = IMDBClient.api_url + api_endpoint,
            headers = self.api_headers
        )
        logging.info('[IMDb] - API endpoint was called: %s', response.request.url)
        media_search = self.__get_details_from_json(media_type, response)

        if not media_search['results']:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND)

        media_info   = []
        media_search = media_search['results']
        for media_id in media_search:
            media_info.append(
                request.state.tmdb.get_media_by_id(request.state.httpx, media_id['guid'], request.state.cache)
                if media_type == 'movie' else
                request.state.tvdb.get_media_by_id(request.state.httpx, media_id['guid'], request.state.cache)
            )
        media_infos = await asyncio.gather(*media_info)

        for media in media_search:
            translation = [ media_info for media_info in media_infos if media_info['guid'] == media['guid'] ]
            if translation:
                media['title'] = translation[0]['title']

        request.state.cache[cache_key] = {'fill_date': time.time(), 'fill_data': []}
        for media_info in media_search:
            request.state.cache[cache_key]['fill_data'].append(media_info['guid'])
            request.state.cache[ media_info['guid'] ] = {'fill_date': time.time(), 'fill_data': media_info}

        return media_search
