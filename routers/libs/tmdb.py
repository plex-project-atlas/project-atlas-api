from starlette.status import HTTP_200_OK

import os
import requests

class tmdb:
    api_url = 'https://api.themoviedb.org/3'

    def __init__(self):
        self.api_key = os.environ['TMDB_API_KEY']

    def search_show_by_name(self, title: str, lang: str = 'it-IT'):
        params = {
            'language': lang,
            'query':    title,
            'api_key':  self.api_key
        }

        res = requests.get(url = tmdb.api_url + '/search/tv', params = params)

        if res.status_code != HTTP_200_OK:
            return None

        json = res.json()

        return [{
            'guid':  item['id'],
            'title': item['title'],
            'year':  item['first_air_date']
        } for item in json['results']]


    def search_movie_by_name(self, title: str, lang: str = 'it-IT'):
        params = {
            'api_key':  self.api_key,
            'language': lang,
            'query':    title
        }

        res = requests.get(url = tmdb.api_url + '/search/movie', params = params)

        if res.status_code != HTTP_200_OK:
            return None

        json = res.json()

        return [{
            'guid':  item['id'],
            'title': item['title'],
            'year':  item['release_date']
        } for item in json['results']]


    def search_all_by_name(self, title: str, lang: str = 'it-IT'):
        params = {
            'api_key':  self.api_key,
            'language': lang,
            'query':    title
        }

        res = requests.get(url = tmdb.api_url + '/search/multi', params = params)

        if res.status_code != HTTP_200_OK:
            return None

        json = res.json()

        results = [{
            'guid':  item['id'],
            'media_type': 'show' if item['media_type'] == 'tv' else 'movie',
            'title': item['title'],
            'year':  item['release_date'] if hasattr(item, 'release_date') else item['first_air_date']
        } for item in json['results']]

        results = []

        for item in json['results']:
            if item['media_type'] in ['movie', 'tv']:
                results.append(item)

        return results

