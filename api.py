import asyncio
import logging
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_restx import Api, Resource, fields

port = 5000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

async def fetch(session, url):
    headers = {
        'User-Agent': 'rohiitgit-WebCrawler/1.0'
    }
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        logger.error(f"Error Fetching URL {url}: {str(e)}")
        return None

async def crawl(url, depth, current_depth=0, visited=None):
    if visited is None:
        visited = set()
    if current_depth > depth or url in visited:
        return {}
    visited.add(url)
    result = {url: [], 'depth': current_depth}

    async with aiohttp.ClientSession() as session:
        html = await fetch(session, url)
        if html is None:
            return result

        soup = BeautifulSoup(html, 'html.parser')
        tasks = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href:
                full_url = urljoin(url, href)
                if is_valid(full_url):
                    result[url].append(full_url)
                    if current_depth < depth:
                        logger.info(f'Crawling {full_url}...')
                        tasks.append(crawl(full_url, depth, current_depth + 1, visited))

        results = await asyncio.gather(*tasks)
        for res in results:
            result.update(res)

    return result

app = Flask(__name__)
api = Api(app, version='1.0', title='rohiitgit - Web Crawler API', description='A simple web crawler API')
ns = api.namespace('api', 'Simple Web Crawler API by github.com/rohiitgit')
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per day", "50 per hour"],
    storage_uri="memcached://localhost:11211",
    storage_options={}
)

crawler_input = api.model('CrawlerInput', {
    'url': fields.String(required=True, description='The URL to crawl'),
    'depth': fields.Integer(required=True, description='The depth of the crawl', default=1, min=1)
})

crawler_response = api.model('CrawlerResponse', {
    'results': fields.Raw(description='The crawled URLs and their links')
})

@ns.route('/crawl')
class CrawlAPI(Resource):
    @limiter.limit("10 per minute")
    @ns.expect(crawler_input)
    @ns.marshal_with(crawler_response)
    def post(self):
        data = request.json
        url = data['url']
        depth = data.get('depth', 1)

        if not url or not is_valid(url):
            api.abort(400, 'Invalid URL')
        if not isinstance(depth, int) or depth < 1:
            api.abort(400, 'Invalid depth')

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(crawl(url, depth))
            loop.close()
            return {'results': results}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            api.abort(500, f"An error occurred: {str(e)}")

if __name__ == '__main__':
    app.run(debug=False, port=port)