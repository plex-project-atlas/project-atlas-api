from pydantic import BaseModel, HttpUrl
from datetime import date
from typing   import List
from enum     import Enum


class SupportedProviders(str, Enum):
    THE_TV_DB    = 'tvdb'
    THE_MOVIE_DB = 'tmdb'

class MediaType(str, Enum):
    MOVIE  = 'movie'
    SERIES = 'series'

class ShowStatus(str, Enum):
    ONGOING   = 'in corso'
    FINISHED  = 'conclusa'
    CANCELLED = 'cancellata'

class Media(BaseModel):
    id:            str     = None
    reference_url: HttpUrl = None
    title:         str     = None
    description:   str     = None
    poster:        HttpUrl = None

class Movie(Media):
    year: str = None

class Season(BaseModel):
    year:           str = None
    episodes_count: int = None

class Show(Media):
    seasons: List[Season] = []
    status:  ShowStatus   = None

class SearchResult(BaseModel):
    movies: List[Movie] = []
    series: List[Show]  = []