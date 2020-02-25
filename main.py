import uvicorn

from fastapi            import FastAPI, Depends
from routers            import match, telegram
from google.cloud       import bigquery
from libs.plex          import PlexClient
from libs.imdb          import IMDBClient
from libs.tmdb          import TMDBClient
from libs.tvdb          import TVDBClient
from libs.models        import env_vars_check
from starlette.requests import Request
from starlette.status   import HTTP_200_OK, \
                               HTTP_503_SERVICE_UNAVAILABLE


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
    clients['bq']   = bigquery.Client()
    clients['plex'] = PlexClient()
    clients['imdb'] = IMDBClient()
    clients['tmdb'] = TMDBClient()
    clients['tvdb'] = TVDBClient()


@app.middleware('http')
async def add_global_vars(request: Request, call_next):
    request.state.bq   = clients['bq']
    request.state.plex = clients['plex']
    request.state.imdb = clients['imdb']
    request.state.tmdb = clients['tmdb']
    request.state.tvdb = clients['tvdb']

    response = await call_next(request)
    return response


app.include_router(
    # import the /match branch of PlexAPI
    match.router,
    prefix    = '/match',
    tags      = ['match'],
    responses = {
        HTTP_200_OK:                  {},
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
