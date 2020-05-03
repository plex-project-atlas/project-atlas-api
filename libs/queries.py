REQ_LIST_QUERY = '''
    SELECT
        MIN(request_date) AS request_date,
        request_id,
        request_season,
        request_status,
        MIN(plex_notes) AS plex_notes,
        COUNT(*) AS request_count
    FROM `plex-project-atlas.project_atlas.plex_user_requests` AS request_data
    GROUP BY request_id, request_season, request_status
    ORDER BY request_count DESC, request_date ASC
'''

REQ_USER_LIST_QUERY = '''
    SELECT
        request_date,
        request_id,
        request_season,
        request_status,
        request_notes,
        plex_notes
    FROM `plex-project-atlas.project_atlas.plex_user_requests` AS request_data
    WHERE user_id = {user_id}
    ORDER BY request_date ASC
'''

REQ_USER_QUERY = '''
    SELECT *
    FROM `plex-project-atlas.project_atlas.plex_user_requests` AS request_data
    WHERE SHA256( CONCAT(request_id, '/', user_id, '/', request_season) ) = FROM_BASE64('{request_code}')
'''

REQ_BY_ID_QUERY = '''
    SELECT
        request_id,
        request_season,
        request_status,
        MIN(plex_notes) AS plex_notes,
        COUNT(*) AS request_count,
        TO_JSON_STRING( ARRAY_AGG(request_data) ) AS request_list
    FROM (
        SELECT *
        FROM `plex-project-atlas.project_atlas.plex_user_requests`
        ORDER BY request_date
    ) AS request_data
    WHERE request_id = '%REQ_ID%'
    GROUP BY request_id, request_season, request_status
    ORDER BY request_count DESC, MIN(request_date) ASC
'''

REQ_INSERT_QUERY = '''
    MERGE INTO
      `plex-project-atlas.project_atlas.plex_user_requests` AS all_requests
    USING (
      SELECT 
        {user_id}        AS user_id,
        "{request_id}"   AS request_id,
        {request_season} AS request_season
    ) AS new_request
    ON
      all_requests.user_id        = new_request.user_id        AND
      all_requests.request_id     = new_request.request_id     AND
      all_requests.request_season = new_request.request_season
    WHEN NOT MATCHED THEN
      INSERT ({fields}) VALUES ({values})
'''

REQ_UPDATE_QUERY = '''
    UPDATE `plex-project-atlas.project_atlas.plex_user_requests`
    SET %UPDATE%
    WHERE SHA256( CONCAT(request_id, '/', user_id, '/', request_season) ) = FROM_BASE64('{request_code}')
'''

REQ_DELETE_QUERY = '''
    DELETE FROM `plex-project-atlas.project_atlas.plex_user_requests`
    WHERE SHA256( CONCAT(request_id, '/', user_id, '/', request_season) ) = FROM_BASE64('{request_code}')
'''
