import os
import requests

from   starlette.status import HTTP_200_OK


class TVDBClient:
    # Ref: https://api.thetvdb.com/swagger (v3.0.0)
    api_url = 'https://api.thetvdb.com'

    def __init__(self, lang: str = 'it'):
        self.usr_name    = os.environ.get('TVDB_USR_NAME')
        self.usr_key     = os.environ.get('TVDB_USR_KEY')
        self.api_key     = os.environ.get('TVDB_API_KEY')
        self.api_headers = {
            'Accept':          'application/vnd.thetvdb.v3.0.0',
            'Content-Type':    'application/json',
            'Authorization':   'Bearer ' + self.get_jwt_token(),
            'Accept-Language': lang
        }

    def get_jwt_token(self):
        headers = {
            'Accept':       'application/json',
            'Content-Type': 'application/json'
        }
        payload = {
            'username': self.usr_name,
            'userkey':  self.usr_key,
            'apikey':   self.api_key
        }
        response = requests.post(url = TVDBClient.api_url + '/login', headers = headers, json = payload)

        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = response.json()
        return resp_obj['token']

    def search_show_by_name(self, title: str):
        params = {
            'name': title
        }
        response = requests.get(url = TVDBClient.api_url + '/search/series', headers = self.api_headers, params = params)

        if response.status_code != HTTP_200_OK:
            return None

        resp_obj = response.json()
        return [{
            'guid':  elem['id'],
            'title': elem['seriesName'],
            'year':  elem['firstAired'].split('-')[0] if elem['firstAired'] else None
        } for elem in resp_obj['data']]
