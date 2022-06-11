import os
import jq
import httpx
import asyncio
import logging
import dateparser

from fastapi          import HTTPException
from typing           import Dict, List
from pydantic         import HttpUrl
from pydantic.tools   import parse_obj_as
from math             import ceil
from libs.utils       import async_ext_api_call
from libs.models      import Episode, MediaType, Media, Movie, SearchResult, Show, Season, MovieStatus, ShowStatus
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY


class TMDBClient:
    source_base_url = 'https://www.themoviedb.org/'

    def __init__(self, http_client: httpx.AsyncClient):
        # Ref: https://developers.themoviedb.org/3 (v3)
        self.api_url     = 'https://api.themoviedb.org/3'
        self.api_key     = os.environ.get('TMDB_API_KEY')
        self.api_headers = {
            'Accept':          'application/json',
            'Content-Type':    'application/json',
        }
        self.http_client = http_client

    async def __get_configs(self) -> Dict:
        # Static until cached (ref: https://developers.themoviedb.org/3/configuration/get-api-configuration)
        return {
            "images": {
                "base_url": "http://image.tmdb.org/t/p/",
                "secure_base_url": "https://image.tmdb.org/t/p/",
                "backdrop_sizes": [
                    "w300",
                    "w780",
                    "w1280",
                    "original"
                ],
                "logo_sizes": [
                    "w45",
                    "w92",
                    "w154",
                    "w185",
                    "w300",
                    "w500",
                    "original"
                ],
                "poster_sizes": [
                    "w92",
                    "w154",
                    "w185",
                    "w342",
                    "w500",
                    "w780",
                    "original"
                ],
                "profile_sizes": [
                    "w45",
                    "w185",
                    "h632",
                    "original"
                ],
                "still_sizes": [
                    "w92",
                    "w185",
                    "w300",
                    "original"
                ]
            }
        }

    async def do_search(self, query: str, type: MediaType = None) -> SearchResult:
        async def do_search_by_type(query: str, type: MediaType, language: str = 'it-IT', page: int = 1) -> List:
            if not type in [MediaType.MOVIE, MediaType.SERIES]:
                detail = '[TMDB] - Unsupported media type requested.'
                logging.error(detail)
                raise HTTPException(status_code = HTTP_422_UNPROCESSABLE_ENTITY, detail = detail)

            api_endpoint = f'/search/{"movie" if type == MediaType.MOVIE else "tv"}'
            response = await async_ext_api_call(
                http_client = self.http_client,
                url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
                method      = httpx.AsyncClient.get,
                caller      = "TMDB",
                headers     = self.api_headers,
                params      = {
                    'api_key':       self.api_key,
                    'language':      language,
                    'query':         query,
                    'page':          page,
                    'include_adult': False
                }
            )
            if page == 1 and response["total_results"] == 0 and language != 'en-US':
                return await do_search_by_type(query = query, type = type, language = 'en-US', page = page)

            search_result = []
            api_configs   = await self.__get_configs()
            for item in response["results"]:
                media = Media(
                    guid       = f'tvdb://{type.value}/{item["id"]}',
                    source_id  = item["id"],
                    source_url = parse_obj_as(HttpUrl,  f'{self.source_base_url}{"movie" if type == MediaType.MOVIE else "tv"}{item["id"]}'),
                    title      = item["title"]          if type == MediaType.MOVIE  and item["title"]          else \
                                 item["original_title"] if type == MediaType.MOVIE  and item["original_title"] else \
                                 item["name"]           if type == MediaType.SERIES and item["name"]           else \
                                 item["original_name"]  if type == MediaType.SERIES and item["original_name"]  else None,
                    overview   = item["overview"]       if item["overview"]        else None,
                    image      = parse_obj_as(HttpUrl,  f'{api_configs["images"]["secure_base_url"]}{api_configs["images"]["poster_sizes"][-1]}{item["poster_path"]}') \
                                 if item["poster_path"] else None,
                    airdate    = dateparser.parse(item["release_date"]).date()   if type == MediaType.MOVIE  and item["release_date"]   else \
                                 dateparser.parse(item["first_air_date"]).date() if type == MediaType.SERIES and item["first_air_date"] else None
                )
                if   type == MediaType.MOVIE:
                    search_result.append( Movie( **media.dict() ) )
                elif type == MediaType.SERIES:
                    search_result.append( Show( **media.dict() ) )

            if page == 1 and int(response["total_pages"]) > 1:
                requests      = [do_search_by_type(query = query, type = type, language = language, page = i) for i in range(2, int(response["total_pages"]) + 1)]
                all_pages     = await asyncio.gather(*requests)
                search_result = search_result + [item for single_page in all_pages for item in single_page]

            return search_result

        if not type:
            results = await asyncio.gather(*[
                do_search_by_type(query = query, type = MediaType.MOVIE),
                do_search_by_type(query = query, type = MediaType.SERIES)
            ])
            return {
                'movies': results[0],
                'series': results[1],
            }

        return {
            'movies': await do_search_by_type(query = query, type = type) if type == MediaType.MOVIE  else [],
            'series': await do_search_by_type(query = query, type = type) if type == MediaType.SERIES else []
        }

    async def get_movie(self, id: int, language: str = 'it-IT') -> Movie:
        api_endpoint = f'/movie/{id}'
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
            method      = httpx.AsyncClient.get,
            caller      = "TMDB",
            headers     = self.api_headers,
            params      = {
                'api_key':  self.api_key,
                'language': language
            }
        )
        api_configs    = await self.__get_configs()
        return Movie(
            guid       = f'tvdb://movie/{response["id"]}',
            source_id  = int(response["id"]),
            source_url = parse_obj_as(HttpUrl, f'{self.source_base_url}movie/{response["id"]}'),
            title      = response["title"]           if response["title"]          else \
                         response["original_title"]  if response["original_title"] else None,
            overview   = response["overview"]        if response["overview"]       else None,
            image      = parse_obj_as(HttpUrl,  f'{api_configs["images"]["secure_base_url"]}{api_configs["images"]["poster_sizes"][-1]}{response["poster_path"]}') \
                         if response["poster_path"]  else None,
            airdate    = dateparser.parse(response["release_date"]).date()  if   response["release_date"] else None,
            runtime    = int(response["runtime"])    if response["runtime"] else None,
            status     = MovieStatus.RUMORED         if response["status"] == 'Rumored'         else \
                         MovieStatus.ANNOUNCED       if response["status"] == 'Planned'         else \
                         MovieStatus.PRE_PRODUCTION  if response["status"] == 'In Production'   else \
                         MovieStatus.POST_PRODUCTION if response["status"] == 'Post Production' else \
                         MovieStatus.RELEASED        if response["status"] == 'Released'        else \
                         MovieStatus.CANCELED        if response["status"] == 'Canceled'        else None
        )

    async def get_show(self, id: int, language: str = 'it-IT', with_episodes: bool = False) -> Show:
        async def get_episodes(show_id: int, number: int, language: str = 'it-IT', api_configs: dict = None) -> List[Episode]:
            api_endpoint = f'/tv/{show_id}/season/{number}'
            response = await async_ext_api_call(
                http_client = self.http_client,
                url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
                method      = httpx.AsyncClient.get,
                caller      = "TMDB",
                headers     = self.api_headers,
                params      = {
                    'api_key':  self.api_key,
                    'language': language
                }
            )
            # ensure episodes are ordered by number
            response["episodes"] = sorted( response["episodes"], key = lambda ep: int(ep["episode_number"]) )

            if not api_configs:
                api_configs = await self.__get_configs()

            episodes      = []
            episode_count = 1
            for episode in response["episodes"]:
                episodes.append( Episode(
                    guid       = f'tvdb://series/{show_id}/episodes/{episode["id"]}',
                    source_id  = episode["id"],
                    source_url = parse_obj_as(HttpUrl, f'{self.source_base_url}tv/{show_id}/season/{number}/{episode["episode_number"]}') \
                                 if "episode_number" in episode   and episode["episode_number"]       else None,
                    title      = episode["name"]     if "name"     in episode and episode["name"]     else None,
                    overview   = episode["overview"] if "overview" in episode and episode["overview"] else None,
                    image      = parse_obj_as(HttpUrl,  f'{api_configs["images"]["secure_base_url"]}{api_configs["images"]["still_sizes"][-1]}{episode["still_path"]}') \
                                 if "still_path" in episode  and episode["still_path"] else None,
                    airdate    = dateparser.parse(response["air_date"]).date() \
                                 if "air_date"   in response and response["air_date"]  else None,
                    number     = episode_count,
                    runtime    = int(episode["runtime"]) if "runtime" in episode and episode["runtime"] else None
                ) )
                episode_count += 1

            return episodes

        api_endpoint = f'/tv/{id}'
        response = await async_ext_api_call(
            http_client = self.http_client,
            url         = parse_obj_as(HttpUrl, self.api_url + api_endpoint),
            method      = httpx.AsyncClient.get,
            caller      = "TMDB",
            headers     = self.api_headers,
            params      = {
                'api_key':  self.api_key,
                'language': language
            }
        )
        api_configs = await self.__get_configs()

        seasons = []
        for season in response["seasons"]:
            seasons.append( Season(
                guid       = f'tvdb://series/{id}/seasons/{season["id"]}',
                source_id  = int(season["id"])  if "id" in season and season["id"]             else None,
                source_url = parse_obj_as(HttpUrl, f'{self.source_base_url}tv/{id}/season/{season["season_number"]}'),
                title      = season["name"]     if "name" in season and season["name"]         else None,
                overview   = season["overview"] if "overview" in season and season["overview"] else None,
                image      = parse_obj_as(HttpUrl, f'{api_configs["images"]["secure_base_url"]}{api_configs["images"]["poster_sizes"][-1]}{season["poster_path"]}') \
                            if "poster_path"    in season and season["poster_path"]            else None,
                airdate    = dateparser.parse(season["air_date"]).date() \
                            if "air_date"       in season and season["air_date"]               else None,
                number     = int(season["season_number"]),
                episodes   = []
            ) )
        # ensure seasons are ordered by number
        seasons = sorted( seasons, key = lambda sn: int(sn.number) )

        if with_episodes:
            episodes = [ get_episodes(show_id = id, number = season.number, language = language, api_configs = api_configs) for season in seasons ]
            episodes = await asyncio.gather(*episodes)
            for index, season in enumerate(seasons):
                season.episodes = episodes[index]

        return Show(
            guid       = f'tvdb://series/{response["id"]}',
            source_id  = int(response["id"]),
            source_url = parse_obj_as(HttpUrl, f'{self.source_base_url}tv/{response["id"]}'),
            title      = response["name"]            if "name"          in response and response["name"]          else \
                         response["original_name"]   if "original_name" in response and response["original_name"] else None,
            overview   = response["overview"]        if "overview"      in response and response["overview"]      else None,
            image      = parse_obj_as(HttpUrl,  f'{api_configs["images"]["secure_base_url"]}{api_configs["images"]["poster_sizes"][-1]}{response["poster_path"]}') \
                         if "poster_path"    in response and response["poster_path"]    else None,
            airdate    = dateparser.parse(response["first_air_date"]).date() \
                         if "first_air_date" in response and response["first_air_date"] else None,
            status     = ShowStatus.UPCOMING if "status" in response and response["status"] == 'In Production'    else \
                         ShowStatus.ONGOING  if "status" in response and response["status"] == 'Returning Series' else \
                         ShowStatus.ENDED    if "status" in response and response["status"] == 'Ended'            else None,
            seasons    = seasons
        )
