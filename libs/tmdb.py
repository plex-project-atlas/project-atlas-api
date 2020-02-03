import os
import requests

from   starlette.status import HTTP_200_OK


class TMDBClient:
    api_url = 'https://api.themoviedb.org/3'

    def __init__(self):
        self.api_key = os.environ.get('TMDB_API_KEY')

    def search_show_by_name(self, title: str, lang: str = 'it-IT'):
        params = {
            'language': lang,
            'query':    title,
            'api_key':  self.api_key
        }
        res = requests.get(url = TMDBClient.api_url + '/search/tv', params = params)

        if res.status_code != HTTP_200_OK:
            return None

        json = res.json()

        return [{
            'guid':  item['id'],
            'title': item['title'],
            'year':  item['first_air_date'].split('-')[0] if item['first_air_date'] else None
        } for item in json['results']]

    def search_movie_by_name(self, title: str, lang: str = 'it-IT'):
        params = {
            'api_key':  self.api_key,
            'language': lang,
            'query':    title
        }
        res = requests.get(url = TMDBClient.api_url + '/search/movie', params = params)

        if res.status_code != HTTP_200_OK:
            return None

        json = res.json()

        return [{
            'guid':  item['id'],
            'title': item['title'],
            'year':  item['release_date'].split('-')[0] if item['release_date'] else None
        } for item in json['results']]

    def search_all_by_name(self, title: str, lang: str = 'it-IT'):
        params = {
            'api_key':  self.api_key,
            'language': lang,
            'query':    title
        }
        res = requests.get(url = TMDBClient.api_url + '/search/multi', params = params)

        if res.status_code != HTTP_200_OK:
            return None

        json    = res.json()
        results = []

        for item in json['results']:
            if item['media_type'] in ['movie', 'tv']:
                year = item['release_date'] if hasattr(item, 'release_date') else item['first_air_date']
                results.append({
                    'guid':  item['id'],
                    'title': item['title'],
                    'type': 'show' if item['media_type'] == 'tv' else 'movie',
                    'year':  year.split('-')[0] if year else None
                })

        return results
