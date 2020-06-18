import time
import httpx
import logging
import uvicorn

from fastapi                 import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers                 import plex, match, search, telegram, requests
from libs.plex               import PlexClient
from libs.imdb               import IMDBClient
from libs.tmdb               import TMDBClient
from libs.tvdb               import TVDBClient
from libs.telegram           import TelegramClient
from libs.requests           import RequestsClient
from libs.models             import env_vars_check
from starlette.requests      import Request
from starlette.status        import HTTP_200_OK, \
                                    HTTP_204_NO_CONTENT, \
                                    HTTP_404_NOT_FOUND, \
                                    HTTP_503_SERVICE_UNAVAILABLE


cache   = {}
clients = {}


def verify_telegram_env_variables():
    required  = [
        'TG_BOT_TOKEN'
    ]
    suggested = []
    env_vars_check(required, suggested)


app = FastAPI(
    title       = 'Project: Atlas - Backend API',
    description = 'API used mainly for Project: Atlas chatbots and tools',
    version     = '1.5.0dev',
    docs_url    = '/',
    redoc_url   = None
)


@app.on_event('startup')
def instantiate_clients():
    logging.info('[FastAPI] - Initializing Plex client...')
    clients['plex']     = PlexClient()
    logging.info('[FastAPI] - Initializing IMDB client...')
    clients['imdb']     = IMDBClient()
    logging.info('[FastAPI] - Initializing TMDB client...')
    clients['tmdb']     = TMDBClient()
    logging.info('[FastAPI] - Initializing TVDB client...')
    clients['tvdb']     = TVDBClient()
    logging.info('[FastAPI] - Initializing Telegram client...')
    clients['telegram'] = TelegramClient()
    logging.info('[FastAPI] - Initializing Requests client...')
    clients['requests'] = RequestsClient()


app.add_middleware(
    CORSMiddleware,
    allow_credentials = True,
    allow_origins     = ['http://localhost:4200'],
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


@app.middleware('http')
async def add_global_vars(request: Request, call_next):
    request.state.cache    = cache
    request.state.plex     = clients['plex']
    request.state.imdb     = clients['imdb']
    request.state.tmdb     = clients['tmdb']
    request.state.tvdb     = clients['tvdb']
    request.state.telegram = clients['telegram']
    request.state.requests = clients['requests']
    request.state.httpx    = httpx.AsyncClient(
        # pool_limits = httpx.PoolLimits(max_connections = 50),
        timeout     = httpx.Timeout(connect_timeout = 60.0),
        http2       = True
    )

    start_time = time.time()
    response = await call_next(request)
    logging.info( '[FastAPI] - The request was completed in: %ss', '{:.2f}'.format(time.time() - start_time) )
    await request.state.httpx.aclose()
    return response


app.include_router(
    # import the /plex branch of PlexAPI
    plex.router,
    prefix    = '/plex',
    tags      = ['plex'],
    responses = {
        HTTP_200_OK:                  {},
        HTTP_204_NO_CONTENT:          {},
        HTTP_503_SERVICE_UNAVAILABLE: {}
    }
)


app.include_router(
    # import the /match branch of PlexAPI
    match.router,
    prefix    = '/match',
    tags      = ['match'],
    responses = {
        HTTP_200_OK:        {},
        HTTP_404_NOT_FOUND: {}
    }
)


app.include_router(
    # import the /search branch of PlexAPI
    search.router,
    prefix    = '/search',
    tags      = ['search'],
    responses = {
        HTTP_200_OK:                  {},
        HTTP_503_SERVICE_UNAVAILABLE: {}
    }
)


app.include_router(
    # import the /requests branch of PlexAPI
    requests.router,
    prefix    = '/requests',
    tags      = ['requests'],
    responses = {
        HTTP_200_OK: {},
        HTTP_204_NO_CONTENT: {},
        HTTP_503_SERVICE_UNAVAILABLE: {}
    }
)


app.include_router(
    # import the /telegram branch of PlexAPI
    telegram.router,
    prefix       = '/telegram',
    tags         = ['telegram'],
    dependencies = [Depends(verify_telegram_env_variables)],
    responses    = {
        HTTP_200_OK:                  {},
        HTTP_503_SERVICE_UNAVAILABLE: {}
    }
)


if __name__ == "__main__":
    uvicorn.run(app, host = "0.0.0.0", port = 8080)
