import os
import httpx
import asyncio
import logging

from   typing           import List
from   starlette.status import HTTP_200_OK


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

        resp_obj = response.json()
        return {
            'query': query,
            'results': [{
                'guid':   'tmdb://' + str(elem['id']),
                'title':  elem['title'] if 'title' in elem else elem['name'],
                'type':   'movie'       if 'title' in elem else 'show',
                'year':   elem['release_date'].split('-')[0]      if 'release_date'   in elem and elem['release_date']   else
                          elem['first_air_date'].split('-')[0]    if 'first_air_date' in elem and elem['first_air_date'] else None,
                'poster': self.img_base_url + elem['poster_path'] if self.img_base_url        and elem['poster_path']    else None
            } for elem in resp_obj['results']]
        }

    async def search_movie_by_name(self, titles: List[str], lang: str = 'it-IT'):
        async def search_worker(client: httpx.AsyncClient, query, query_lang: str, headers: dict):
            api_endpoint = '/search/movie'
            params = {
                'language': query_lang,
                'query':    query
            }
            logging.info('[TMDb] - Calling API endpoint: %s', TMDBClient.api_url + api_endpoint)
            response = await client.get(url = TMDBClient.api_url + api_endpoint, headers = headers, params = params)
            return self.__get_show_details_from_json(query, response)

        httpx_client = httpx.AsyncClient()
        requests     = (search_worker(httpx_client, elem.strip(), lang, self.api_headers) for elem in titles)
        responses    = await asyncio.gather(*requests)
        return responses

    async def search_show_by_name(self, titles: List[str], lang: str = 'it-IT'):
        async def search_worker(client: httpx.AsyncClient, query, query_lang: str, headers: dict):
            api_endpoint = '/search/tv'
            params = {
                'language': query_lang,
                'query':    query
            }
            logging.info('[TMDb] - Calling API endpoint: %s', TMDBClient.api_url + api_endpoint)
            response = await client.get(url = TMDBClient.api_url + api_endpoint, headers = headers, params = params)
            return self.__get_show_details_from_json(query, response)

        httpx_client = httpx.AsyncClient()
        requests     = (search_worker(httpx_client, elem.strip(), lang, self.api_headers) for elem in titles)
        responses    = await asyncio.gather(*requests)
        return responses
