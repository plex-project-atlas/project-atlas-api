import os
import json
import logging

from   fastapi             import HTTPException
from   google.cloud        import bigquery
from   libs.queries        import REQ_LIST_QUERY, REQ_BY_ID_QUERY
from   starlette.status    import HTTP_404_NOT_FOUND, \
                                  HTTP_500_INTERNAL_SERVER_ERROR


class RequestsClient:
    def __init__(self):
        self.bq_client = bigquery.Client()

    def get_requests_list(self, pendent_only: bool = True):
        query     = REQ_LIST_QUERY
        query_job = self.bq_client.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        try:
            results = query_job.result()
        except:
            logging.error('[BQ] - Error retrieving users requests')
            raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

        requests = []
        for request in results:
            requests.append({
                'request_date':   str(request['request_date']),
                'request_id':     request['request_id'],
                'request_type':   request['request_type'],
                'request_season': request['request_season'],
                'request_status': request['request_status'],
                'plex_notes':     request['plex_notes'],
                'request_count':  request['request_count']
            })

        return requests if not pendent_only else [ request for request in requests if request['request_status'] == 'WAIT']

    def get_request(self, request_id):
        query       = REQ_BY_ID_QUERY.replace('%REQ_ID%', request_id)
        query_job   = self.bq_client.query(query, project = os.environ['DB_PROJECT'], location = os.environ['DB_REGION'])
        try:
            results = query_job.result()
        except:
            logging.error('[BQ] - Error retrieving users requests')
            raise HTTPException(status_code = HTTP_500_INTERNAL_SERVER_ERROR, detail = 'Internal Server Error')

        if results.total_rows == 0:
            raise HTTPException(status_code = HTTP_404_NOT_FOUND, detail = 'Not Found')

        request_info = next( iter(results) )
        request_info = {
            'request_id':     request_info['request_id'],
            'request_type':   request_info['request_type'],
            'request_season': request_info['request_season'],
            'request_status': request_info['request_status'],
            'plex_notes':     request_info['plex_notes'],
            'request_count':  request_info['request_count'],
            'request_list':   request_info['request_list']
        }
        return request_info
