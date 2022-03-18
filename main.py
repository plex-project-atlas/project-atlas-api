import time
import httpx
import asyncio
import logging
import uvicorn

from fastapi                 import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers                 import plex, match, search, telegram, requests
from sqlalchemy.orm          import Session
#from .database.database      import SessionLocal, db_engine
#from .database               import crud, models, schemas
from libs.plex               import PlexClient
from libs.tmdb               import TMDBClient
from libs.tvdb               import TVDBClient
from libs.scraper            import ScraperClient
#from libs.requests           import RequestsClient
from starlette.requests      import Request
from starlette.status        import HTTP_200_OK, \
                                    HTTP_204_NO_CONTENT, \
                                    HTTP_404_NOT_FOUND, \
                                    HTTP_503_SERVICE_UNAVAILABLE


cache   = {}
clients = {}

#models.BaseModel.metadata.create_all(bind = db_engine)

app = FastAPI(
    title       = 'Project: Atlas - Backend API',
    description = 'API used mainly for Project: Atlas chatbots and tools',
    version     = '1.5.0dev',
    docs_url    = '/',
    redoc_url   = None,
    debug       = True
)


""" def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() """


@app.on_event('startup')
async def instantiate_clients():
    logging.getLogger('filelock').disabled = True
    logging.getLogger('plexapi').disabled  = True

    logging.info('[FastAPI] - Initializing HTTPX client...')
    clients['httpx']    = httpx.AsyncClient(
        limits    = httpx.Limits(max_connections = 50),
        timeout   = httpx.Timeout(60.0),
        http2     = True,
        transport = httpx.AsyncHTTPTransport(
            retries = 5
        )
    )
    logging.info('[FastAPI] - Initializing Plex client...')
    clients['plex']     = PlexClient()
    logging.info('[FastAPI] - Initializing TMDB client...')
    clients['tmdb']     = TMDBClient()
    logging.info('[FastAPI] - Initializing TVDB client...')
    #clients['tvdb']     = TVDBClient(clients['httpx'])
    #await clients['tvdb'].do_authenticate()
    logging.info('[FastAPI] - Initializing Scraper client...')
    clients['scraper']  = ScraperClient(clients['httpx'])
    #await asyncio.gather(*[clients['scraper'].do_login(website) for website in clients['scraper'].config['sources']])
    logging.info('[FastAPI] - Initializing Requests client...')
    #clients['requests'] = RequestsClient()

    # logging.getLogger('plexapi').disabled = False


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
    request.state.httpx    = clients['httpx']
    request.state.plex     = clients['plex']
    request.state.tmdb     = clients['tmdb']
    #request.state.tvdb     = clients['tvdb']
    request.state.scraper  = clients['scraper']
    #request.state.requests = clients['requests']

    start_time = time.time()
    response = await call_next(request)
    logging.info( '[FastAPI] - The request was completed in: %ss', '{:.2f}'.format(time.time() - start_time) )
    # await request.state.httpx.aclose()
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


""" app.include_router(
    # import the /telegram branch of PlexAPI
    telegram.router,
    prefix       = '/telegram',
    tags         = ['telegram'],
    dependencies = [Depends(verify_telegram_env_variables)],
    responses    = {
        HTTP_200_OK:                  {},
        HTTP_503_SERVICE_UNAVAILABLE: {}
    }
) """


if __name__ == "__main__":
    # LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(pathname)s:%(lineno)d [%(name)s] %(levelprefix)s %(message)s"
    uvicorn.run(app, host = "0.0.0.0", port = 8080)
