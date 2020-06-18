import os
import httpx
import asyncio
import logging

from   fastapi             import APIRouter, Depends, Response
from   typing              import List
from   libs.models         import verify_plex_env_variables, Media
from   starlette.requests  import Request
from   starlette.status    import HTTP_204_NO_CONTENT


router = APIRouter()


@router.get(
    '/show/list',
    summary        = 'Retrieve Plex show list',
    dependencies   = [ Depends(verify_plex_env_variables) ],
    response_model = List[Media]
)
async def match_id(request: Request):
    """
    Retrieve a list of all Plex TV Shows with IDs and present episodes
    """
    return request.state.plex.get_show_list()


@router.get(
    '/show/missing',
    summary        = 'Retrieve Plex show missing episodes',
    dependencies   = [ Depends(verify_plex_env_variables) ],
    response_model = None
)
async def match_id(request: Request):
    """
    Retrieve a list of all show episodes which are currently missing from Plex
    """
    logging.info('[Plex] - Retrieving complete show inventory...')
    plex_show_inventory  = request.state.plex.get_show_list()
    logging.info('[Plex] - Inventory completed, retrieving show updates...')
    tvdb_show_updates    = [
        request.state.tvdb.get_media_by_id(
            httpx_client = request.state.httpx,
            media_id     = show.guid,
            media_cache  = request.state.cache,
            info_only    = False
        ) for show in plex_show_inventory if show.guid.startswith('tvdb')
    ]
    tvdb_show_updates    = await asyncio.gather(*tvdb_show_updates)
    logging.info('[Plex] - Show info retrieval completed.')

    missing_elements = []
    for tvdb_show in tvdb_show_updates:
        plex_show = [ show for show in plex_show_inventory if show.guid == tvdb_show['guid'] ]
        if not plex_show:
            continue
        plex_show = plex_show[0]

        for season_num, season in enumerate(tvdb_show['seasons']):
            # Skipping specials
            if season_num == 0:
                continue

            missing_episodes = []
            for episode_num, episode in enumerate(season['episodes']):
                if season_num == 0 or episode_num == 0 or \
                not episode or not episode['translated']:
                    continue

                if  plex_show.seasons and season_num <= len(plex_show.seasons) - 1 and plex_show.seasons[season_num] \
                and plex_show.seasons[season_num].episodes and episode_num <= len(plex_show.seasons[season_num].episodes) - 1 \
                and plex_show.seasons[season_num].episodes[episode_num]:
                    continue
                missing_episodes.append({
                    'showTitle':           tvdb_show['title'],
                    'showYear':            tvdb_show['year'],
                    'elementType':         'episode',
                    'elementData':         {
                        'episodeSeason':       season_num,
                        'episodeNumber':       episode_num,
                        'episodeTitle':        episode['title'],
                        'episodeFirstAirDate': episode['first_air_date']
                    }
                })
            if (
                season_num > len(plex_show.seasons) - 1
                and len(missing_episodes) > 1
            ) or len(missing_episodes) == len(season['episodes']) - 1:
                missing_elements.append({
                    'showTitle':   tvdb_show['title'],
                    'showYear':    tvdb_show['year'],
                    'elementType': 'season',
                    'elementData': {
                        'seasonNumber':      season_num,
                        'seasonLength':      len(season['episodes']) - 1,
                        'seasonLastAirDate': season['episodes'][-1]['first_air_date'] \
                                             if season['episodes'] and season['episodes'][-1] else None
                    }
                })
            else:
                missing_elements += missing_episodes

    # send update to Google Apps Script endpoint
    try:
        httpx.post(os.environ.get('GS_ENDPOINT'), json = {'action': 'missing', 'data': missing_elements})
    except httpx.ReadTimeout:
        pass

    return Response(status_code = HTTP_204_NO_CONTENT)
