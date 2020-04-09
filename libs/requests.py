import os
import json
import logging

from   google.cloud import bigquery
from   libs.queries import REQ_LIST_QUERY


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
            results = []

        requests = []
        for request in results:
            request_list = []
            for request_data in json.loads(request['request_list']):
                request_list.append({
                    'request_date':    request_data['request_date'],
                    'user_id':         request_data['user_id'],
                    'user_name':       request_data['user_name'],
                    'user_first_name': request_data['user_first_name'],
                    'user_last_name':  request_data['user_last_name'],
                    'request_notes':   request_data['request_notes']
                })
            requests.append({
                'request_id':     request['request_id'],
                'request_type':   request['request_type'],
                'request_season': request['request_season'],
                'request_status': request['request_status'],
                'plex_notes':     request['plex_notes'],
                'request_count':  request['request_count'],
                'request_list':   request_list
            })

        return requests if not pendent_only else\
               [ request for request in requests if request['request_status'] == 'WAIT']
