from ast import Param
import os
import jq
import httpx
import asyncio
import dateparser

from typing           import List
from pydantic         import HttpUrl
from pydantic.tools   import parse_obj_as
from math             import ceil
from libs.utils       import async_ext_api_call
from libs.models      import MediaType, Media, Movie, Show, Season, Episode, \
                             SearchResult, MovieStatus, ShowStatus, SeasonType
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

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

    async def do_search(self, query: str, type: MediaType = None) -> SearchResult:
        api_endpoint = '/search'
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
            method      = httpx.AsyncClient.get,
            caller      = "TVDB",
            headers     = await self.get_auth_headers(),
            params      = {
                'query'   : query,
                'type'    : type.value
            } if type else {'query': query}
        )

        search_result = {
            'movies': [],
            'series': []
        }
        for item in response["data"]:
            if not item["type"] in ["movie", "series"]:
                continue

            media = Media(
                guid      = f'tvdb://{item["type"]}/{item["tvdb_id"]}',
                source_id = int(item["tvdb_id"]),
                title     = item["translations"]["ita"] if "translations" in item and "ita" in item["translations"]  else \
                            item["translations"]["eng"] if "translations" in item and "eng" in item["translations"]  else item["name"],
                overview  = item["overviews"]["ita"]    if "overviews"    in item and "ita" in item["overviews"]     else \
                            item["overviews"]["eng"]    if "overviews"    in item and "eng" in item["overviews"]     else \
                            item["overview"]            if "overview"     in item else None,
                image     = parse_obj_as(HttpUrl, item["thumbnail"]) if "thumbnail" in item and item["thumbnail"] else parse_obj_as(HttpUrl, item["image_url"]),
                airdate   = dateparser.parse(item["first_air_time"]).date()  if "first_air_time" in item and item["first_air_time"] else \
                            dateparser.parse("01/01/" + item["year"]).date() if "year"           in item and item["year"]           else None
            )

            if item["type"] == "movie":
                search_result["movies"].append(Movie(
                    **media.dict() | {
                        'source_url': parse_obj_as(HttpUrl, f'{self.movies_url_prefix}{item["slug"]}') if "slug" in item and item["slug"] else None,
                        'status':     (
                            MovieStatus.ANNOUNCED       if item["status"].lower() in MovieStatus.ANNOUNCED.value.lower()       else \
                            MovieStatus.PRE_PRODUCTION  if item["status"].lower() in MovieStatus.PRE_PRODUCTION.value.lower()  else \
                            MovieStatus.POST_PRODUCTION if item["status"].lower() in MovieStatus.POST_PRODUCTION.value.lower() else \
                            MovieStatus.COMPLETED       if item["status"].lower() in MovieStatus.COMPLETED.value.lower()       else \
                            MovieStatus.RELEASED        if item["status"].lower() in MovieStatus.RELEASED.value.lower()        else None
                        ) if "status" in item and item["status"] else None
                    }
                ) )
            else:
                search_result["series"].append(Show(
                    **media.dict() | {
                        'source_url': parse_obj_as(HttpUrl, f'{self.series_url_prefix}{item["slug"]}') if "slug" in item and item["slug"] else None,
                        'status':     (
                            ShowStatus.UPCOMING if item["status"].lower() in ShowStatus.UPCOMING.value.lower() else \
                            ShowStatus.ONGOING  if item["status"].lower() in ShowStatus.ONGOING.value.lower()  else \
                            ShowStatus.ONGOING  if item["status"].lower() in "Continuing".lower()              else \
                            ShowStatus.ENDED    if item["status"].lower() in ShowStatus.ENDED.value.lower()    else None
                        ) if "status" in item  and item["status"] else None
                    }
                ) )

        return search_result

    async def get_movie(self, id: int) -> Movie:
        api_endpoint = f'/movies/{id}/extended'
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
            method      = httpx.AsyncClient.get,
            caller      = "TVDB",
            headers     = await self.get_auth_headers(),
            params      = {
                'meta':  'translations',
                'short': 'true'
            }
        )
        return Movie(
            guid       = f'tvdb://movie/{response["data"]["id"]}',
            source_id  = int(response["data"]["id"]),
            source_url = parse_obj_as(HttpUrl, f'{self.movies_url_prefix}{response["data"]["slug"]}') if 'slug' in response["data"] else None,
            title      = next(
                (translation for translation in response["data"]["translations"]["nameTranslations"] if translation["language"] == "ita"),
                next(
                    (translation for translation in response["data"]["translations"]["nameTranslations"] if translation["language"] == "eng"),
                    {"name": response["data"]["name"]}
                )
            )["name"],
            overview   = next(
                (translation for translation in response["data"]["translations"]["overviewTranslations"] if translation["language"] == "ita"),
                next(
                    (translation for translation in response["data"]["translations"]["overviewTranslations"] if translation["language"] == "eng"),
                    {"overview": None}
                )
            )["overview"],
            image      = parse_obj_as(HttpUrl, response["data"]["image"]) if 'image' in response["data"] else None,
            airdate    = dateparser.parse(response["data"]["first_release"]["date"]).date() if 'date' in response["data"]["first_release"] else None,
            runtime    = response["data"]["runtime"] if response["data"]["runtime"] else None,
            status     = MovieStatus.ANNOUNCED       if response["data"]["status"]["id"] == 1 else \
                         MovieStatus.PRE_PRODUCTION  if response["data"]["status"]["id"] == 2 else \
                         MovieStatus.POST_PRODUCTION if response["data"]["status"]["id"] == 3 else \
                         MovieStatus.COMPLETED       if response["data"]["status"]["id"] == 4 else \
                         MovieStatus.RELEASED        if response["data"]["status"]["id"] == 5 else None
        )

    async def get_show(self, id: int, season_type: SeasonType = SeasonType.OFFICIAL, with_episodes: bool = False) -> Show:
        async def get_seasons(show_id: int, season_type: SeasonType, language: str = None, page: int = 0) -> List[Season]:
            jq_season_parser = '''[ .data.episodes | group_by(.seasonNumber)[] | {
                guid:     ( "tvdb://series/" + (.[0].seriesId | tostring) + "/seasons/" + (.[0].seasonNumber | tostring) ),
                number:   .[0].seasonNumber,
                episodes: [ .[] | {
                    guid:       ( "tvdb://series/" + (.seriesId | tostring) + "/episodes/" + (.id | tostring) ),
                    source_id:  (.id | tonumber),
                    source_url: ( "/episodes/" + (.id | tostring) ),
                    title:      .name,
                    overview:   .overview,
                    image:      .image,
                    airdate:    .aired,
                    number:     .number,
                    runtime:    .runtime
                } ]
            } ]'''

            api_endpoint = f'/series/{id}/episodes/{season_type}'
            if language:
                api_endpoint += f'/{language}'

            response = await async_ext_api_call(
                http_client = self.http_client,
                url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
                method      = httpx.AsyncClient.get,
                caller      = "TVDB",
                headers     = await self.get_auth_headers(),
                params      = {
                    'page': page
                }
            )
            tmp_seasons = jq.compile(jq_season_parser).input(response).first()

            seasons = []
            for tmp_season in tmp_seasons:
                episodes = []
                for tmp_episode in tmp_season["episodes"]:
                    episodes.append( Episode( **tmp_episode | {
                        "source_url": parse_obj_as(HttpUrl, f'{self.series_url_prefix}{response["data"]["series"]["slug"]}{tmp_episode["source_url"]}'),
                        "title":      tmp_episode["title"]    if tmp_episode["title"]    else "",
                        "overview":   tmp_episode["overview"] if tmp_episode["overview"] else None,
                        "image":      parse_obj_as(HttpUrl, tmp_episode["image"])     if tmp_episode["image"]   else None,
                        "airdate":    dateparser.parse(tmp_episode["airdate"]).date() if tmp_episode["airdate"] else None
                    } ) )
                seasons.append( Season( **tmp_season | {
                    "source_url": parse_obj_as(HttpUrl, f'{self.series_url_prefix}{response["data"]["series"]["slug"]}/seasons/{season_type.value.lower()}/{tmp_season["number"]}'),
                    "episodes":   episodes
                } ) )

            if page == 0 and (response["links"]["total_items"] / response["links"]["page_size"]) > 1:
                requests = []
                for i in range( 1, ceil(response["links"]["total_items"] / response["links"]["page_size"]) ):
                    requests.append( self.get_seasons(id = id, season_type = season_type, language = language, page = i) )
                all_pages = await asyncio.gather(*requests)
                all_pages = seasons + [item for single_page in all_pages for item in single_page]

                seasons = []
                for tmp_season in all_pages:
                    index = next((i for i, season in enumerate(seasons) if season.guid == tmp_season.guid), None)
                    if not index:
                        seasons.append(tmp_season)
                    else:
                        seasons[index].episodes += tmp_season.episodes

                # order seasons and episodes by number
                for season in seasons:
                    season.episodes = sorted(season.episodes, key = lambda ep: ep.number)
                seasons = sorted(seasons, key = lambda sn: sn.number)

            return seasons

        api_endpoint = f'/series/{id}/extended'
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
            method      = httpx.AsyncClient.get,
            caller      = "TVDB",
            headers     = await self.get_auth_headers(),
            params      = {
                'meta':  'translations',
                'short': 'true'
            }
        )

        seasons = []
        for season in response["data"]["seasons"]:
            if not season["type"]["type"].lower() == season_type.value.lower():
                continue
            seasons.append( Season(
                guid       = f'tvdb://series/{id}/seasons/{season["id"]}',
                source_id  = int(season["id"]),
                source_url = parse_obj_as(HttpUrl, f'{self.series_url_prefix}{response["data"]["slug"]}/seasons/{season_type.value.lower()}/{season["number"]}'),
                image      = parse_obj_as(HttpUrl, season["image"]) \
                             if "image" in season and season["image"] else None,
                number     = int(season["number"]),
                episodes   = []
            ) )
        # ensure seasons are ordered by number
        seasons = sorted( seasons, key = lambda sn: int(sn.number) )

        if with_episodes:
            ep_seasons = await get_seasons(show_id = id, season_type = season_type)
            for season in seasons:
                for ep_season in ep_seasons:
                    if ep_season.source_url == season.source_url:
                        season.episodes = ep_season.episodes
                        if not season.airdate and ep_season.episodes[0].airdate:
                            season.airdate = ep_season.episodes[0].airdate
                        break

        return Show(
            guid       = f'tvdb://series/{response["data"]["id"]}',
            source_id  = int(response["data"]["id"]),
            source_url = parse_obj_as(HttpUrl, f'{self.series_url_prefix}{response["data"]["slug"]}') if 'slug' in response["data"] else None,
            title      = next(
                (translation for translation in response["data"]["translations"]["nameTranslations"] if translation["language"] == "ita"),
                next(
                    (translation for translation in response["data"]["translations"]["nameTranslations"] if translation["language"] == "eng"),
                    {"name": response["data"]["name"]}
                )
            )["name"],
            overview   = next(
                (translation for translation in response["data"]["translations"]["overviewTranslations"] if translation["language"] == "ita"),
                next(
                    (translation for translation in response["data"]["translations"]["overviewTranslations"] if translation["language"] == "eng"),
                    {"overview": None}
                )
            )["overview"],
            image      = parse_obj_as(HttpUrl, response["data"]["image"]) if 'image' in response["data"] else None,
            airdate    = dateparser.parse(response["data"]["firstAired"]).date() if response["data"]["firstAired"] else None,
            status     = ShowStatus.UPCOMING if response["data"]["status"]["id"] == 3 else \
                         ShowStatus.ONGOING  if response["data"]["status"]["id"] == 1 else \
                         ShowStatus.ENDED    if response["data"]["status"]["id"] == 2 else None,
            seasons    = seasons
        )
