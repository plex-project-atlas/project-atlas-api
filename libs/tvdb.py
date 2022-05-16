import os
import httpx
import logging

from pydantic       import HttpUrl
from pydantic.tools import parse_obj_as
from libs.utils     import async_ext_api_call
from cachetools     import cached, LRUCache, TTLCache
from libs.models    import MediaType, Media, Movie, Show, ShowStatus

class TVDBClient:
    series_url_prefix = 'https://thetvdb.com/series/'
    movies_url_prefix = 'https://thetvdb.com/movies/'

    def __init__(self, http_client: httpx.AsyncClient):
        # Ref: https://thetvdb.github.io/v4-api (v4.6.2)
        self.api_url     = 'https://api4.thetvdb.com/v4'
        self.usr_pin     = os.environ.get('TVDB_USR_PIN')
        self.api_key     = os.environ.get('TVDB_API_KEY')
        self.api_headers = {
            'Accept':          'application/json',
            'Content-Type':    'application/json',
        }
        self.http_client = http_client

    #@cached(cache=TTLCache(maxsize=1, ttl=604800)) # Cache token for 1 week
    async def get_auth_token(self):
        api_endpoint = '/login'
        payload = {
            'pin':    self.usr_pin,
            'apikey': self.api_key
        }
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
            method      = httpx.AsyncClient.post,
            caller      = "TVDB",
            headers     = self.api_headers,
            json        = payload
        )
        return response['data']['token']

    async def get_auth_headers(self):
        return self.api_headers | { 'Authorization': f'Bearer { await self.get_auth_token() }' }

    async def search(self, language: str, type: MediaType, query: str):
        api_endpoint = '/search'
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
            method      = httpx.AsyncClient.get,
            caller      = "TVDB",
            headers     = await self.get_auth_headers(),
            params      = {
                'query'   : query,
                'type'    : 'movie' if type == MediaType.MOVIE else ('series' if type == MediaType.SHOW else ''),
                'language': language
            }
        )

        if len(response['data']) == 0 and language != 'eng':
            return await self.search('eng', type, query)

        result = [ ]
        for item in response['data']:
            media = Media(
                title=item['translations'][language] if 'translations' in item and language in item['translations'] else item['name'],
                description=item['overviews'][language] if 'overviews' in item and language in item['overviews'] else item['overview'] if 'overview' in item else '',
                poster=parse_obj_as(HttpUrl, item['thumbnail']) if 'thumbnail' in item else None,
            )

            result.append(
                Movie(
                    **media.dict() | {
                        'id': f'tvdb://movie/{item["id"]}',
                        'reference_url': parse_obj_as(HttpUrl, f'{self.movies_url_prefix}{item["slug"]}') if 'slug' in item else None,
                        'year': item['year'] if 'year' in item else ''
                    }
                ) if item['type'] == 'movie' else
                Show(
                    **media.dict() | {
                        'id': f'tvdb://series/{item["id"]}',
                        'reference_url': parse_obj_as(HttpUrl, f'{self.series_url_prefix}{item["slug"]}') if 'slug' in item else None,
                        'status': ShowStatus.FINISHED if not 'status' in item or item['status'] == 'Ended' else ShowStatus.ONGOING if item['status'] == 'Continuing' else ShowStatus.CANCELLED
                    }
                )
            )
        return result
