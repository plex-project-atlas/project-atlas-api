import os
import sys
import uvicorn

from fastapi          import FastAPI
from routers          import match

app = FastAPI(
    title       = 'Project: Atlas - Backend API',
    description = 'API used mainly for Project: Atlas chatbots and tools',
    version     = '1.0.0dev',
    docs_url    = '/',
    redoc_url   = None
)


app.include_router(
    # import the /match branch of PlexAPI
    match.router,
    prefix = '/match',
    tags   = ['match']
)


if __name__ == "__main__":
    uvicorn.run(app, host = "0.0.0.0", port = 8080)
