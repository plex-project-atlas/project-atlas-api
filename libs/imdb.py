import os
import re
import json
import httpx
import asyncio
import logging
import urllib.parse

from   typing           import List
from   libs.queries     import IMDB_SHOW_QUERY, \
                               IMDB_MOVIE_FULL_QUERY, \
                               IMDB_MOVIE_TRANSLATION_QUERY
from   google.cloud     import bigquery
from   starlette.status import HTTP_200_OK


class IMDBClient:
    api_url = 'https://sg.media-imdb.com'

    def __init__(self, lang: str = 'it'):
        self.api_headers = {
            'Accept': 'application/json'
        }
        self.bq_client = bigquery.Client()

    @staticmethod
    def __get_details_from_json(query, query_type: str, response: httpx.Response):
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
                    'guid':   'imdb://' + elem['id'],
                    'title':  elem['l'],
                    'type':   'show'       if elem['q'] == 'TV series' else 'movie',
                    'year':   elem['y']    if 'y' in elem              else None,
                    'poster': elem['i'][0] if 'i' in elem              else None
                })

        return {
            'query':   query,
            'results': [item for item in results if item['type'] == query_type] if query_type else results
        }

    async def get_media_by_id(self, imdb_ids: List[str], media_type: str, trans_only: bool = False, lang: str = 'IT'):
        query = IMDB_MOVIE_TRANSLATION_QUERY if trans_only \
                else IMDB_MOVIE_FULL_QUERY if media_type == 'movie' else IMDB_SHOW_QUERY
        query = query.replace( '%IMDB_IDS%', ','.join("'{0}'".format(imdb_id) for imdb_id in imdb_ids) )
        query = query.replace( '%LANG%', lang.upper() )

        query_job = self.bq_client.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        try:
            results = query_job.result()
        except:
            logging.error('[BQ] - Error while retrieving media %s', 'translations' if trans_only else 'infos')
            logging.error('[BQ] - Involved IDs: %s', ', '.join( "'{0}'".format(imdb_id) for imdb_id in imdb_ids) )
            results = []

        if results and results.total_rows:
            try:
                results = [json.loads(result['mediaInfo']) for result in results]
            except:
                logging.error('[IMDb] - Error while parsing database media translations')
                results = []

        return results

    async def search_media_by_name(self, titles: List[str], media_type: str, lang: str = 'IT'):
        async def search_worker(client: httpx.AsyncClient, query, query_type: str, headers: dict):
            api_endpoint = '/suggests/' + query[0].lower() + '/' + urllib.parse.quote(query, safe = '') + '.json'
            logging.info('IMDBClient - Calling API endpoint: %s', IMDBClient.api_url + api_endpoint)
            response = await client.get(url = IMDBClient.api_url + api_endpoint, headers = headers)
            return self.__get_details_from_json(query, query_type, response)

        httpx_client = httpx.AsyncClient()
        requests     = (search_worker(httpx_client, elem.strip(), media_type, self.api_headers) for elem in titles)
        responses    = await asyncio.gather(*requests)

        imdb_ids     = [ result['guid'].split('://')[1] for response in responses for result in response['results'] ]
        media_infos  = await self.get_media_by_id(imdb_ids, media_type, True)

        for response in responses:
            for result in response['results']:
                translation = [ media for media in media_infos if result['guid'].endswith(media['titleId']) ]
                if translation:
                    result['title'] = translation[0]['titleData'][0]['title']

        return responses
