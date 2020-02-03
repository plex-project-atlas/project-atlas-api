import os
import sys
import uvicorn

from fastapi          import FastAPI, Depends, HTTPException
from routers          import match
from starlette.status import HTTP_415_UNSUPPORTED_MEDIA_TYPE

app = FastAPI()


async def verify_media_type(media_type: str):
    if media_type not in ['movie', 'show']:
        raise HTTPException(status_code = HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail = "Unsupported Media Type")


app.include_router(
    # import the /match branch of PlexAPI
    match.router,
    prefix = '/match',
    tags   = ['match'],
    dependencies = [ Depends(verify_media_type) ]
)


if __name__ == "__main__":
    uvicorn.run(app, host = "0.0.0.0", port = 8080)
