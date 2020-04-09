import uvicorn

from fastapi            import FastAPI, Depends
from routers            import match, search, telegram, requests
from libs.plex          import PlexClient
from libs.imdb          import IMDBClient
from libs.tmdb          import TMDBClient
from libs.tvdb          import TVDBClient
from libs.telegram      import TelegramClient
from libs.requests      import RequestsClient
from libs.models        import env_vars_check
from starlette.requests import Request
from starlette.status   import HTTP_200_OK, \
                               HTTP_204_NO_CONTENT, \
                               HTTP_404_NOT_FOUND, \
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
    clients['plex']     = PlexClient()
    clients['imdb']     = IMDBClient()
    clients['tmdb']     = TMDBClient()
    clients['tvdb']     = TVDBClient()
    clients['telegram'] = TelegramClient()
    clients['requests'] = RequestsClient()


@app.middleware('http')
async def add_global_vars(request: Request, call_next):
    request.state.plex     = clients['plex']
    request.state.imdb     = clients['imdb']
    request.state.tmdb     = clients['tmdb']
    request.state.tvdb     = clients['tvdb']
    request.state.telegram = clients['telegram']
    request.state.requests = clients['requests']

    response = await call_next(request)
    return response


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
    prefix = '/requests',
    tags   = ['requests'],
    responses={
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
