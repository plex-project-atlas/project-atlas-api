import os
import re
import yaml
import httpx
import asyncio
import logging
import dateparser
import tldextract

from   fastapi          import HTTPException
from   typing           import Dict
from   libs.commons     import async_ext_api_call
from   fake_useragent   import UserAgent, FakeUserAgentError
from   bs4              import BeautifulSoup, SoupStrainer
from   starlette.status import HTTP_200_OK


class ScraperClient:
    def __init__(self, httpx_client: httpx.AsyncClient):
        # load scraper inventory and configs
        with open('libs/config/scraper.yaml') as config:
            try:
                self.config = yaml.load(config, Loader = yaml.FullLoader)
            except yaml.YAMLError:
                logging.error('[Scraper] - Unable to load scraper configuration')
                exit(1)

        self.timezone = 'Europe/Rome'

        # simulate a real browser request
        default_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0'  # FF 87
        try:
            user_agent = UserAgent(fallback = default_user_agent)
            user_agent.update(cache = False)
            user_agent = user_agent.random
        except FakeUserAgentError:
            user_agent = default_user_agent
        self.headers = {
            'User-Agent':   user_agent,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        self.session = httpx_client

    async def do_login(self, website: Dict):
        # prepraing the request
        protocol   = 'https' if website['use_ssl'] else 'http'
        login_path = website["login_path"] if website["login_path"] else ''
        login_url  = f'{protocol}://{website["domain"]}{login_path}'
        payload    = {
            self.config['scrapers'][ website['scraper']['id'] ]['login']['username']: os.getenv(
                f'SCRAPER__SITE_{website["name"].upper()}_USER',
                default = os.getenv('SCRAPER__SITE_DEFAULT_USER', default = '')
            ),
            self.config['scrapers'][website['scraper']['id']]['login']['password']: os.getenv(
                f'SCRAPER__SITE_{website["name"].upper()}_PASS',
                default = os.getenv('SCRAPER__SITE_DEFAULT_PASS', default = '')
            )
        }
        for extra in self.config['scrapers'][website['scraper']['id']]['login']['extra']:
            for key in extra:
                payload[key] = extra[key]

        # making an async request
        try:
            response = await async_ext_api_call(
                http_client     = self.session,
                url             = login_url,
                use_post        = True,
                parse_json      = False,
                caller          = website['name'],
                headers         = self.headers,
                data            = payload,
                allow_redirects = True
            )
        except HTTPException:
            logging.warning(f'[Scraper] - Connection error, website disabled: {website["name"]}')
            website['enabled'] = False
            return None

        # check for asserts
        try:
            assert response.status_code == HTTP_200_OK
            for check in self.config['scrapers'][website['scraper']['id']]['login']['assert']:
                for key in check:
                    if key.lower() == 'cookie':
                        # check for both specific and root domains
                        assert self.session.cookies.get(name = check[key], domain = website['domain']) or \
                               self.session.cookies.get(
                                   name   = check[key],
                                   domain = f'.{tldextract.extract(website["domain"]).registered_domain}'
                               )
                        logging.info(f'[Scraper] - Login successful: {website["name"]}')
                        website['enabled'] = True
        except AssertionError:
            logging.warning(f'[Scraper] - Login failed, website disabled: {website["name"]}')
            website['enabled'] = False

    async def do_search(self, website: Dict, query: str, page: int = 1, result: int = 1):
        def get_quality(title: str):
            quality_list = [
                '4320p/8K',
                '2160p/4K',
                '1440p/WQHD/QHD',
                '1080p/FullHD/Full HD',
                '720p/HDReady/HD Ready',
                '576p', '480p', '360p', '240p', '144p'
            ]
            quality_regex = re.compile(
                r'(4320|8K|2160|4K|1440|WQHD|QHD|1080|FullHD|Full\sHD|720|HDReady|HD\sReady|576|480|360|240|144)[pi]*',
                re.IGNORECASE)

            quality_match = quality_regex.search(title)
            if quality_match is None:
                return str(len(quality_list) + 1) + '. Altro'
            else:
                for i, quality in enumerate(quality_list, start = 1):
                    if quality_match.group(1) in quality:
                        return str(i).zfill(2) + '. ' + quality_list[i - 1].split('/')[0]

            # should not be needed
            return str(len(quality_list) + 1) + '. Altro'

        page_results = []
        this_results = []
        next_results = []

        # preparing the request
        protocol    = 'https' if website['use_ssl'] else 'http'
        search_path = website["search_path"] if website["search_path"] else ''
        search_url  = f'{protocol}://{website["domain"]}{search_path}'
        payload = {
            self.config['scrapers'][website['scraper']['id']]['search']['query']: query,
            self.config['scrapers'][website['scraper']['id']]['search']['starting_page']: page,
            self.config['scrapers'][website['scraper']['id']]['search']['starting_result']: result
        }
        for extra in self.config['scrapers'][website['scraper']['id']]['search']['extra']:
            for key in extra:
                payload[key] = extra[key] if not extra[key] is None else ''
        # applying site's overrides
        if 'search' in website and 'override' in website['search'] and website['search']['override']:
            for override in website['search']['override']:
                for key in override:
                    payload[key] = override[key]

        # making an async request
        try:
            logging.info(f'[Scraper] - External DDL results are being retrieved: {search_url}')
            response = await self.session.post(
                url             = search_url,
                headers         = self.headers,
                data            = payload,
                allow_redirects = True
            )
        except httpx.ConnectError:
            logging.warning(f'[Scraper] - Connection error, page skipped: {website["name"]}/P{page}')
            return []
        except httpx.TimeoutException:
            logging.warning(f'[Scraper] - Connection timeout, page skipped: {website["name"]}/P{page}')
            return []

        # check for asserts
        try:
            assert response.status_code == HTTP_200_OK
        except AssertionError:
            logging.error(f'[Scraper] - Error retrieving search results page ({page}/{result}): {website["name"]}')
            return []

        # find last page
        if page == 1:
            onclick  = self.config['scrapers'][website['scraper']['id']]['search']['navigator']['onclick']
            strainer = SoupStrainer(
                self.config['scrapers'][website['scraper']['id']]['search']['navigator']['tag'],
                onclick = re.compile(rf'{onclick}') if onclick else False,
                href    = self.config['scrapers'][website['scraper']['id']]['search']['navigator']['href'],
                id      = self.config['scrapers'][website['scraper']['id']]['search']['navigator']['id']
            )
            page_list = BeautifulSoup(
                response.content,
                from_encoding = website['encoding'] if 'encoding' in website else None,
                features      = 'lxml',
                parse_only    = strainer
            )
            page_list = page_list.find_all('a')
            if page_list:
                last_page = int(page_list[-1].text)
                page_results = asyncio.gather(*[self.do_search(
                    website = website,
                    query   = query,
                    page    = next_page
                ) for next_page in range(2, last_page + 1)])

        # parse results
        strainer = SoupStrainer(
            self.config['scrapers'][website['scraper']['id']]['search']['strainer']['tag'],
            id = self.config['scrapers'][website['scraper']['id']]['search']['strainer']['id']
        )
        elements = BeautifulSoup(
            response.content,
            from_encoding = website['encoding'] if 'encoding' in website else None,
            features      = 'lxml',
            parse_only    = strainer
        )
        elements = elements.select(website["scraper"]["element"]["selector"])
        for idx, element in enumerate(elements, start = 1):
            title_tag = element.select(website['scraper']['element']['title_selector']) \
                        if website['scraper']['element']['title_selector'] else [element]
            date_tag  = element.select(website['scraper']['element']['date_selector']) \
                        if website['scraper']['element']['date_selector'] else [element]
            if 'date_regexp' in website['scraper']['element'] and date_tag:
                matcher  = re.search(website['scraper']['element']['date_regexp'], date_tag[0].text, re.IGNORECASE)
                date_val = dateparser.parse(matcher.group(1), settings = {'TIMEZONE': self.timezone}) \
                           if matcher else None
            else:
                date_val  = dateparser.parse(date_tag[0].text.strip(), settings = {'TIMEZONE': self.timezone}) \
                            if date_tag else None
            link_tag  = element.select(website['scraper']['element']['link_selector']) \
                        if website['scraper']['element']['link_selector'] else [element]
            if all([title_tag, link_tag]):
                this_results.append({
                    'title':   title_tag[0].text.strip(),
                    'quality': get_quality( title_tag[0].text.strip() ),
                    'date':    date_val,
                    'link':    link_tag[0]['href'].strip()
                })
            else:
                logging.warning(f'[Scraper] - Error parsing result, skipping result ({idx})')

        logging.info(f'[Scraper] - External DDL results retrieved (P/R): {page}/{len(this_results)}')
        if page == 1:
            if page_results:
                next_results = [element for results in (await page_results) for element in results]
            logging.info(
                f'[Scraper] - A total of {len(this_results) + len(next_results)} were found for: {website["name"]}'
            )
        return this_results + next_results

