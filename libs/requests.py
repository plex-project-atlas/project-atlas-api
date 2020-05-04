import os
import json
import logging

from   fastapi             import HTTPException
from   datetime            import datetime
from   google.cloud        import bigquery
from   libs.models         import Request
from   libs.queries        import REQ_LIST_QUERY, \
                                  REQ_USER_QUERY, \
                                  REQ_BY_ID_QUERY, \
                                  REQ_INSERT_QUERY, \
                                  REQ_UPDATE_QUERY, \
                                  REQ_DELETE_QUERY, \
                                  REQ_USER_LIST_QUERY
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
            raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR)

        return results

    def get_requests_list(self, pendent_only: bool = True, user_id: int = None):
        query    = REQ_LIST_QUERY if not user_id else REQ_USER_LIST_QUERY.format(user_id = user_id)
        results  = self.__perform_query_job(query)

        requests = [{
            'request_date':   str(request['request_date']),
            'request_id':     request['request_id'],
            'request_season': request['request_season'],
            'request_status': request['request_status'],
            'plex_notes':     request['plex_notes'],
            'request_count':  request['request_count']
        } for request in results] if not user_id else [{
            'request_date':   str(request['request_date']),
            'request_id':     request['request_id'],
            'request_season': request['request_season'],
            'request_status': request['request_status'],
            'request_notes':  request['request_notes'],
            'plex_notes':     request['plex_notes']
        } for request in results]
        return requests if not pendent_only else [ request for request in requests if request['request_status'] == 'WAIT']

    async def get_request(self, media_cache: dict, request_id: str = None, request_code: str = None):
        if not any([request_id, request_code]):
            logging.error('[Requests] - No filter provided for request search')
            raise HTTPException(status_code = HTTP_404_NOT_FOUND)

        query   = REQ_USER_QUERY if request_code else REQ_BY_ID_QUERY
        query   = query.format(request_id = request_id, request_code = request_code)
        results = self.__perform_query_job(query)

        if results.total_rows == 0:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND)

        request_info = next( iter(results) )
        request_info = {
            "request_date":    request_info['request_date'],
            "user_id":         request_info['user_id'],
            "user_name":       request_info['user_name'],
            "user_first_name": request_info['user_first_name'],
            "user_last_name":  request_info['user_last_name'],
            "request_id":      request_info['request_id'],
            "request_season":  request_info['request_season'],
            "request_notes":   request_info['request_notes'],
            "request_status":  request_info['request_status'],
            "plex_notes":      request_info['plex_notes']
        } if request_code else {
            'request_id':      request_info['request_id'],
            'request_season':  request_info['request_season'],
            'request_status':  request_info['request_status'],
            'plex_notes':      request_info['plex_notes'],
            'request_count':   request_info['request_count'],
            'request_list':    request_info['request_list']
        }
        return request_info

    async def insert_request(self, request_payload: Request):
        params = request_payload.dict()
        params['request_date']   = datetime.today().strftime('%Y-%m-%d')
        params['request_status'] = 'WAIT'
        if not params['request_season']:
            params['request_season'] = -1
        query  = REQ_INSERT_QUERY.format(
            user_id        = params['user_id'],
            request_id     = params['request_id'],
            request_season = params['request_season'],
            fields         = ', '.join([ var for var in params if params[var] ]),
            values         = ', '.join([ str(params[var]) if isinstance(params[var], int) else
                                         '"{}"'.format(params[var]) for var in params if params[var] ])
        )

        result = self.__perform_query_job(query)

        return result.total_rows > 0

    async def patch_request(self, request_payload: Request, request_code: str = None):
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

        if any([request_payload.request_season is not None, request_payload.plex_notes]) and not request_code:
            logging.error('[Requests] - Cannot update season or user notes without providing a request code')
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
        query  = query.format(
            updates    = ', '.join(update),
            condition  = "request_id = '{request_id}'".format(request_id = request_payload.request_id)
                         if not request_code else
                         "SHA256(CONCAT(request_id, '/', user_id, '/', request_season)) = FROM_BASE64('{request_code}')"
                         .format(request_code = request_code)
        )
        result = self.__perform_query_job(query)

        return result.total_rows > 0

    async def delete_request(self, request_code: str):
        query = REQ_DELETE_QUERY
        query = query.format(request_code = request_code)

        result = self.__perform_query_job(query)

        return result.total_rows > 0
