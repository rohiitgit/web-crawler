import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import logging
from flask import Flask, request
from flask_restx import Api, Resource, fields
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def crawl(url, depth, current_depth=0, visited=None):
    if visited is None:
        visited = set()
    if current_depth > depth or url in visited:
        return {}
    visited.add(url)
    result = {url: [], 'depth': current_depth}
    try:
        headers = {
            'User-Agent': 'MyWebCrawler/1.0 (+http://example.com/bot)'
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a'):
            href = link.get('href')
            if href:
                full_url = urljoin(url, href)
                if is_valid(full_url):
                    result[url].append(full_url)
                    if current_depth < depth:
                        logger.info(f'Crawling {full_url}...')
                        result.update(crawl(full_url, depth, current_depth + 1, visited))
        time.sleep(1)  # Be polite, wait 1 second between requests
    except requests.RequestException as e:
        logger.error(f'Error crawling URL {url}: {str(e)}')
        logger.info('Continuing with other links...')
    return result

app = Flask(__name__)
api = Api(app, version='1.0', title='Web Crawler API', description='A simple web crawler API')
ns = api.namespace('api', 'Simple Web Crawler API Operations')

# Set up rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
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
            results = crawl(url, depth)
            return {'results': results}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            api.abort(500, f"An error occurred: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)