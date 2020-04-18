import os
import json
import logging

from   fastapi             import HTTPException
from   google.cloud        import bigquery
from   libs.models         import RequestPayload
from   libs.queries        import REQ_LIST_QUERY, REQ_BY_ID_QUERY, REQ_INSERT_QUERY
from   starlette.status    import HTTP_404_NOT_FOUND, \
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

    async def insert_request(self, request_payload: RequestPayload):
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
