import os
import re
import time
import logging
import plexapi.exceptions

from   fastapi          import HTTPException
from   typing           import List
from   libs.models      import Media, Season, Episode
from   plexapi.myplex   import MyPlexAccount, PlexClient, PlexServer
from   starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR


CACHE_VALIDITY = 86400  # 1 day


class PlexClient:
    def __init__(self):
        logging.getLogger('urllib3').setLevel(logging.ERROR)

        try:
            self.plex_client = MyPlexAccount(token = os.environ['PLEXAPI_AUTH_CLIENT_TOKEN'])\
                               .resource(os.environ['PLEXAPI_AUTH_SRV_NAME']).connect(ssl = True)
        except plexapi.exceptions.NotFound:
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

    def get_show_list(self) -> List[Media]:
        plex_show_list = []
        for section in self.plex_client.library.sections():
            if section.type.lower() != 'show':
                continue
            for show in section.all():
                # extract TTVDB ID for the show
                id_search = re.search('\.(thetvdb|themoviedb):\/\/(\d{5,}).*$', show.guid, re.IGNORECASE)
                if not id_search:
                    logging.warning('[Plex] - Show agent isn\'t TVDb nor TMDb: ' + show.title)
                    logging.warning('[Plex] - Plex show agent: ' + show.guid)
                    continue

                show_entry = Media(
                    guid    = ('tvdb' if id_search.group(1) == 'thetvdb' else 'tmdb') + '://show/' + id_search.group(2),
                    title   = show.title,
                    type    = 'show',
                    year    = show.year,
                    poster  = show.thumbUrl,
                    seasons = []
                )

                for season in show.seasons():
                    # fill season array with placeholders
                    while len(show_entry.seasons) < season.index + 1:
                        show_entry.seasons.append(None)
                    show_entry.seasons[season.index] = Season(episodes = [])
                    for episode in season.episodes():
                        # fill episode array with placeholders
                        while len(show_entry.seasons[season.index].episodes) < episode.index + 1:
                            show_entry.seasons[season.index].episodes.append(False)
                        show_entry.seasons[season.index].episodes[episode.index] = True

                plex_show_list.append(show_entry)

        return plex_show_list
