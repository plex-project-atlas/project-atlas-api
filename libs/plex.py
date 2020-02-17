import os

from   typing           import List
from   plexapi.myplex   import MyPlexAccount, PlexServer


class PlexClient:
    def __init__(self):
        try:
            self.plex_client =  MyPlexAccount().resource(os.environ['PLEXAPI_AUTH_SRV_NAME'])
            self.plex_client =  PlexServer(token = self.plex_client.accessToken)
        except:
            self.plex_client =  None

    def search_media_by_name(self, titles: List[str], media_type: str):
        results = []
        for title in titles:
            try:
                plex_results = self.plex_client.search(query = title.strip(), mediatype = media_type)
                results.append({
                    'query':   title.strip(),
                    'results': [{
                        'guid':  elem.guid,
                        'title': elem.title,
                        'type':  elem.type,
                        'year':  elem.year
                    } for elem in plex_results if elem.type == media_type]
                })
            except:
                return None

        return results

    def search_movie_by_name(self, titles: List[str]):
        return self.search_media_by_name(titles, 'movie')

    def search_show_by_name(self, titles: List[str]):
        return self.search_media_by_name(titles, 'show')
