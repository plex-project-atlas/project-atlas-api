import os
import json
import logging

from   fastapi             import HTTPException
from   google.cloud        import bigquery
from   libs.models         import Request
from   libs.queries        import REQ_LIST_QUERY, \
                                  REQ_BY_ID_QUERY, \
                                  REQ_INSERT_QUERY, \
                                  REQ_UPDATE_QUERY, \
                                  REQ_DELETE_QUERY
from   starlette.status    import HTTP_400_BAD_REQUEST, \
                                  HTTP_404_NOT_FOUND, \
                                  HTTP_500_INTERNAL_SERVER_ERROR


class RequestsClient:
    def __init__(self):
        self.bq_client = bigquery.Client()

    def __perform_query_job(self, query: str):
        query_job = self.bq_client.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        try:
            results = query_job.result()
        except:
            logging.error('[BQ] - Error while executing query: %s', query)
            raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

        return results

    def get_requests_list(self, pendent_only: bool = True):
        query    = REQ_LIST_QUERY
        results  = self.__perform_query_job(query)

        requests = []
        for request in results:
            requests.append({
                'request_date':   str(request['request_date']),
                'request_id':     request['request_id'],
                'request_season': request['request_season'],
                'request_status': request['request_status'],
                'plex_notes':     request['plex_notes'],
                'request_count':  request['request_count']
            })
        return requests if not pendent_only else [ request for request in requests if request['request_status'] == 'WAIT']

    async def get_request(self, request_id):
        query   = REQ_BY_ID_QUERY.replace('%REQ_ID%', request_id)
        results = self.__perform_query_job(query)

        if results.total_rows == 0:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND, detail = 'Not Found')

        request_info = next( iter(results) )
        request_info = {
            'request_id':     request_info['request_id'],
            'request_season': request_info['request_season'],
            'request_status': request_info['request_status'],
            'plex_notes':     request_info['plex_notes'],
            'request_count':  request_info['request_count'],
            'request_list':   request_info['request_list']
        }
        return request_info

    async def insert_request(self, request_payload: Request):
        params = request_payload.dict()
        query  = REQ_INSERT_QUERY
        query  = query.replace('%FIELDS%', ', '.join([ var for var in params if params[var] ]))
        query  = query.replace(
            '%VALUES%',
            ', '.join([ str(params[var]) if isinstance(params[var], int) else '"{}"'.format(params[var])
            for var in params if params[var] ])
        )

        result = self.__perform_query_job(query)

        return result.total_rows > 0

    async def patch_request(self, request_payload: Request):
        if not any([
            request_payload.request_season,
            request_payload.request_notes,
            request_payload.request_status,
            request_payload.plex_notes
        ]):
            logging.error('[Requests] - None of the updatable request field was submitted')
            raise HTTPException(status_code = HTTP_400_BAD_REQUEST, detail = 'Bad Request')

        if any([
            request_payload.request_season,
            request_payload.request_notes
        ]) and any([
            request_payload.request_status,
            request_payload.plex_notes
        ]):
            logging.error('[Requests] - Cannot update global and specific fields all together')
            raise HTTPException(status_code = HTTP_400_BAD_REQUEST, detail = 'Bad Request')

        if request_payload.request_season and 'movie' in request_payload.request_id:
            logging.error('[Requests] - Cannot update season number of a movie request')
            raise HTTPException(status_code = HTTP_400_BAD_REQUEST, detail = 'Bad Request')

        update = []
        query  = REQ_UPDATE_QUERY
        if request_payload.request_season:
            update.append( 'request_season = {}'.format(request_payload.request_season)   )
        if request_payload.request_notes:
            update.append( 'request_notes  = "{}"'.format(request_payload.request_notes)  )
        if request_payload.request_status:
            update.append( 'request_status = "{}"'.format(request_payload.request_status) )
        if request_payload.plex_notes:
            update.append( 'plex_notes     = "{}"'.format(request_payload.plex_notes)     )
        query  = query.replace('%UPDATE%', ', '.join(update))
        query  = query.replace('%REQ_ID%', request_payload.request_id)
        if any([request_payload.request_season, request_payload.request_notes]):
            query = query + ' AND user_id = %USR_ID%'.replace( '%USR_ID%', str(request_payload.user_id) )

        result = self.__perform_query_job(query)

        return result.total_rows > 0

    async def delete_request(self, request_payload: Request):
        query = REQ_DELETE_QUERY
        query = query.format(request_id = request_payload.request_id, user_id = request_payload.user_id)

        result = self.__perform_query_job(query)

        return result.total_rows > 0
