import os
import re
import time
import logging

from   fastapi          import HTTPException
from   typing           import List
from   plexapi.myplex   import MyPlexAccount, PlexServer
from   starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR


CACHE_VALIDITY = 86400  # 1 day


class PlexClient:
    def __init__(self):
        try:
            self.plex_client =  MyPlexAccount().resource(os.environ['PLEXAPI_AUTH_SRV_NAME'])
            self.plex_client =  PlexServer(token = self.plex_client.accessToken)
        except:
            self.plex_client =  None

    def search_media_by_name(self, media_titles: List[str], media_type: str, media_cache: dict):
        results = []
        for media_title in media_titles:
            cache_key = 'plex://search/' + media_type + '/' + re.sub(r'\W', '_', media_title.strip())
            if cache_key in media_cache and time.time() - media_cache[cache_key]['fill_date'] < CACHE_VALIDITY:
                logging.info('[Plex] - Cache hit for key: %s', cache_key)
                results.append(media_cache[cache_key]['fill_data'])
            else:
                try:
                    plex_results = self.plex_client.search(query = media_title.strip(), mediatype = media_type) if media_title else []
                    logging.info('[Plex] - Search was forwarded to server: %s', media_title.strip())
                    results.append({
                        'query':   media_title.strip(),
                        'results': [{
                            'guid':  'plex://' + elem.guid.split('://')[1].split('?')[0],
                            'title': elem.title,
                            'type':  elem.type,
                            'year':  str(elem.year)
                        } for elem in plex_results if elem.type == media_type]
                    })
                    media_cache[cache_key] = { 'fill_date': time.time(), 'fill_data': results[-1] }
                except:
                    raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

        if len(results) == 1 and not results[0]['results']:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND, detail = 'Not Found')

        return results

    def search_movie_by_name(self, titles: List[str]):
        return self.search_media_by_name(titles, 'movie')

    def search_show_by_name(self, titles: List[str]):
        return self.search_media_by_name(titles, 'show')
