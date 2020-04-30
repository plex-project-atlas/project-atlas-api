import os
import re
import time
import logging

from   fastapi          import HTTPException
from   typing           import List
from   libs.models      import Media
from   plexapi.myplex   import MyPlexAccount, PlexServer
from   starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR


CACHE_VALIDITY = 86400  # 1 day


class PlexClient:
    def __init__(self):
        try:
            self.plex_client = MyPlexAccount().resource(os.environ['PLEXAPI_AUTH_SRV_NAME'])
            self.plex_client = PlexServer(token = self.plex_client.accessToken)
        except:
            self.plex_client = None

    def search_media_by_name(self, media_title, media_type: str, media_cache: dict) -> List[Media]:
        cache_key = 'plex://search/' + media_type + '/' + re.sub(r'\W', '_', media_title.strip())
        if cache_key in media_cache and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
            logging.info('[Plex] - Cache hit for key: %s', cache_key)
            return media_cache[cache_key]['fill_data']

        try:
            plex_results = self.plex_client.search(query = media_title.strip(), mediatype = media_type)
            logging.info('[Plex] - Search was forwarded to server: %s', media_title.strip())
            media_search = [{
                'guid':  'plex://' + media_type + '/' + elem.guid.split('://')[1].split('?')[0],
                'title': elem.title,
                'type':  elem.type,
                'year':  str(elem.year)
            } for elem in plex_results if elem.type == media_type]
            media_cache[cache_key] = {'fill_date': time.time(), 'fill_data': media_search}
        except:
            raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR)

        if not media_search:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND)

        return media_search
