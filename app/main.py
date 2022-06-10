import os
import time
import httpx
import uvicorn
import logging
import warnings

from fastapi            import FastAPI, HTTPException, Depends
from libs.tvdb          import TVDBClient
from libs.tmdb          import TMDBClient
from routers            import search, details
from starlette.requests import Request
from starlette.status   import HTTP_200_OK, \
                               HTTP_500_INTERNAL_SERVER_ERROR, \
                               HTTP_511_NETWORK_AUTHENTICATION_REQUIRED


clients = {}


async def verify_dependencies():
    if not all([
        os.environ.get('TVDB_USR_PIN'),
        os.environ.get('TVDB_API_KEY')
    ]):
        raise HTTPException(
            status_code = HTTP_511_NETWORK_AUTHENTICATION_REQUIRED,
            detail      = '[TVDB] - Missing API authentication'
        )

app = FastAPI(
    title        = 'Project: Atlas - Backend API',
    description  = 'API used mainly for Project: Atlas and tools',
    version      = '0.0.1',
    docs_url     = '/',
    redoc_url    = None,
    debug        = True,
    dependencies = [ Depends(verify_dependencies) ]
)


@app.on_event('startup')
async def instantiate_clients():
    logging.info('[FastAPI] - Initializing HTTPX client...')
    clients['httpx'] = httpx.AsyncClient(
        limits    = httpx.Limits(max_connections = 50),
        timeout   = httpx.Timeout(60.0),
        http2     = True,
        transport = httpx.AsyncHTTPTransport(
            retries = 1 # TODO: I nostri retry in async_ext_api_call() non tengono conto di questo
        )
    )
    logging.info('[FastAPI] - Initializing TVDB client...')
    clients['tvdb'] = TVDBClient(clients['httpx'])
    logging.info('[FastAPI] - Initializing TMDB client...')
    clients['tmdb'] = TMDBClient(clients['httpx'])

@app.middleware('http')
async def add_global_vars(request: Request, call_next):
    request.state.httpx = clients['httpx']
    request.state.tvdb  = clients['tvdb']
    request.state.tmdb  = clients['tmdb']

    start_time = time.time()
    response = await call_next(request)
    logging.info( '[FastAPI] - The request was completed in: %ss', '{:.2f}'.format(time.time() - start_time) )
    # await request.state.httpx.aclose()
    return response


# import the /search branch of PlexAPI
app.include_router(
    search.router,
    prefix    = '/search',
    tags      = ['search'],
    responses = {
        HTTP_200_OK: {}
    }
)

# import the /details branch of PlexAPI
app.include_router(
    details.router,
    prefix    = '/details',
    tags      = ['details'],
    responses = {
        HTTP_200_OK: {}
    }
)


if __name__ == '__main__':
    # WORKAROUND for https://github.com/scrapinghub/dateparser/issues/1013
    warnings.filterwarnings(
        "ignore",
        message = "The localize method is no longer necessary, as this time zone supports the fold attribute",
    )
    uvicorn.run(app,
        host   = os.environ.get('UVICORN_HOST',      '0.0.0.0'),
        port   = int( os.environ.get('UVICORN_PORT', '8080') ),
        #reload = os.environ.get('UVICORN_RELOAD', 'True')
    )