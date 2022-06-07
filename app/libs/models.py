import re

from pydantic import BaseModel, HttpUrl, ValidationError, validator
from datetime import date
from typing   import List
from enum     import Enum


class SupportedProviders(str, Enum):
    THE_TV_DB    = 'tvdb'
    THE_MOVIE_DB = 'tmdb'

class MediaType(str, Enum):
    MOVIE  = 'movie'
    SERIES = 'series'

class MovieStatus(str, Enum):
    ANNOUNCED       = 'Announced'
    PRE_PRODUCTION  = 'Pre-Production'
    POST_PRODUCTION = 'Filming / Post-Production'
    COMPLETED       = 'Completed'
    RELEASED        = 'Released'

class ShowStatus(str, Enum):
    UPCOMING = 'Upcoming'
    ONGOING  = 'Ongoing'
    ENDED    = 'Ended'

class Media(BaseModel):
    guid:       str
    source_id:  int
    source_url: HttpUrl = None
    title:      str
    overview:   str     = None
    image:      HttpUrl = None
    airdate:    date    = None

class Movie(Media):
    runtime: int         = None
    status:  MovieStatus = None

    @validator('guid')
    def guid_format(cls, guid):
        if not re.match(r'^(tmdb|tvdb):\/\/movie\/\d+$', guid):
            raise ValueError('[Media] - Wrong movie GUID.')
        return guid

class Episode(Media):
    number:  int
    runtime: int = None

    @validator('guid')
    def guid_format(cls, guid):
        if not re.match(r'^(tmdb|tvdb):\/\/series\/\d+\/episodes\/\d+$', guid):
            raise ValueError('[Media] - Wrong episode GUID.')
        return guid

class Season(BaseModel):
    guid:     str
    number:   int
    episodes: List[Episode]

    @validator('guid')
    def guid_format(cls, guid):
        if not re.match(r'^(tmdb|tvdb):\/\/series\/\d+\/seasons\/\d+$', guid):
            raise ValueError('[Media] - Wrong season GUID.')
        return guid

class Show(Media):
    seasons: List[Season] = []
    status:  ShowStatus   = None

    @validator('guid')
    def guid_format(cls, guid):
        if not re.match(r'^(tmdb|tvdb):\/\/series\/\d+$', guid):
            raise ValueError('[Media] - Wrong episode GUID.')
        return guid

class SearchResult(BaseModel):
    movies: List[Movie] = []
    series: List[Show]  = []