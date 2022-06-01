import os
import time
import httpx
import uvicorn
import logging

from fastapi            import FastAPI, HTTPException, Depends
from libs.tvdb          import TVDBClient
from routers            import search
from starlette.requests import Request
from starlette.status   import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

clients = {}

async def verify_dependencies():
    if not all([
            os.environ.get('TVDB_USR_PIN'),
            os.environ.get('TVDB_API_KEY')
        ]):
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Missing TVDB API Tokens'
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

@app.middleware('http')
async def add_global_vars(request: Request, call_next):
    request.state.httpx = clients['httpx']
    request.state.tvdb  = clients['tvdb']

    start_time = time.time()
    response = await call_next(request)
    logging.info( '[FastAPI] - The request was completed in: %ss', '{:.2f}'.format(time.time() - start_time) )
    # await request.state.httpx.aclose()
    return response

@app.get('/')
def root():
    a = "a"
    b = "b" + a
    return {"hello world": b}

app.include_router(
    # import the /match branch of PlexAPI
    search.router,
    prefix    = '/search',
    tags      = ['search'],
    responses = {
        HTTP_200_OK:        {}
    }
)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)