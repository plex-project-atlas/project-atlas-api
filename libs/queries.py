IMDB_MOVIE_FULL_QUERY = '''
    SELECT TO_JSON_STRING( STRUCT(
        basics.tconst        AS mediaTitleId,
        basics.originalTitle AS mediaOriginalTitle,
        akas.title           AS mediaTranslatedTitle,
        basics.startYear     AS mediaYear
    ), true) as mediaInfo
    FROM
        project_atlas.imdb_title_basics AS basics LEFT JOIN
        project_atlas.imdb_title_akas   AS akas   ON basics.tconst = akas.titleId
    WHERE
        basics.tconst IN (%IMDB_IDS%) AND ( UPPER(akas.region) = '%LANG%' OR UPPER(akas.language) = '%LANG%' )
'''

IMDB_MOVIE_TRANSLATION_QUERY = '''
    SELECT TO_JSON_STRING( STRUCT(
        titleId,
        ARRAY_AGG( STRUCT(
          SAFE_CAST(ordering AS INT64) AS ordering,
          title,
          language,
          region
        ) ORDER BY SAFE_CAST(ordering AS INT64) ASC) AS titleData
    ) ) AS mediaInfo
    FROM `project_atlas.imdb_title_akas`
    WHERE titleId IN (%IMDB_IDS%) AND (UPPER(region) = '%LANG%' OR UPPER(language) = '%LANG%')
    GROUP BY titleId
    ORDER BY titleId
'''

IMDB_SHOW_QUERY  = '''
    WITH episodes_akas AS (
        SELECT
            episodes.parentTconst  AS parentTitleId,
            basics.tconst          AS titleId,
            basics.originalTitle,
            akas.title             AS translatedTitle,
            episodes.seasonNumber,
            episodes.episodeNumber
        FROM 
            `plex-project-atlas.project_atlas.imdb_title_episodes` AS episodes
            INNER JOIN
            `plex-project-atlas.project_atlas.imdb_title_basics`   AS basics ON basics.tconst = episodes.tconst
            LEFT JOIN (
                SELECT *
                FROM   `plex-project-atlas.project_atlas.imdb_title_akas`
                WHERE  UPPER(region) = '%LANG%' OR UPPER(language) = '%LANG%'
            ) AS akas  ON akas.titleId  = basics.tconst    
        WHERE    episodes.parentTconst IN (%IMDB_IDS%)
        ORDER BY episodes.seasonNumber, episodes.episodeNumber
    )
    
    SELECT
        TO_JSON_STRING( STRUCT(
            episodes_akas.parentTitleId AS mediaTitleId,
            basics.originalTitle        AS mediaOriginalTitle,
            akas.title                  AS mediaTranslatedTitle,
            basics.startYear            AS mediaYear,
            ARRAY_AGG( STRUCT (
                episodes_akas.titleId         AS episodeTitleId,
                episodes_akas.originalTitle   AS episodeOriginalTitle,
                episodes_akas.translatedTitle AS episodeTranslatedTitle,
                episodes_akas.seasonNumber,    
                episodes_akas.episodeNumber
        ) ORDER BY episodes_akas.seasonNumber ASC, episodes_akas.episodeNumber ASC) AS episodesData) ) AS mediaInfo
    FROM        episodes_akas
    LEFT JOIN   (
         SELECT *
         FROM   `plex-project-atlas.project_atlas.imdb_title_akas`
         WHERE   UPPER(region) = '%LANG%' OR UPPER(language) = '%LANG%'
    )    AS akas ON episodes_akas.parentTitleId = akas.titleId
    INNER JOIN  `plex-project-atlas.project_atlas.imdb_title_basics` AS basics ON episodes_akas.parentTitleId = basics.tconst
    GROUP BY     episodes_akas.parentTitleId, basics.originalTitle, akas.title, basics.startYear
'''

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

REQ_INSERT_QUERY = 'INSERT INTO `plex-project-atlas.project_atlas.plex_user_requests`(%FIELDS%) VALUES (%VALUES%)'

REQ_UPDATE_QUERY = '''
    UPDATE `plex-project-atlas.project_atlas.plex_user_requests`
    SET %UPDATE%
    WHERE request_id = "%REQ_ID%"
'''

REQ_DELETE_QUERY = '''
    DELETE FROM `plex-project-atlas.project_atlas.plex_user_requests`
    WHERE request_id = "{request_id}" AND user_id = {user_id}
'''
