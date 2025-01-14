import asyncio
import logging
from urllib.parse import urljoin, urlparse
import os
import aiohttp
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_restx import Api, Resource, fields
import redis
import prometheus_client
from prometheus_client import Counter, Histogram
import unittest
import time
from healthcheck import HealthCheck
from apscheduler.schedulers.background import BackgroundScheduler
import sys

# Prometheus metrics
REQUESTS = Counter('crawler_requests_total', 'Total crawler requests')
ERRORS = Counter('crawler_errors_total', 'Total crawler errors')
CRAWL_TIME = Histogram('crawler_processing_seconds', 'Time spent processing request')

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Redis configuration with connection pooling
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis-11229.c238.us-central1-2.gce.redns.redis-cloud.com')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_POOL = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, db=0)

def get_redis():
    return redis.Redis(connection_pool=REDIS_POOL)

# Health check function
def redis_available():
    try:
        r = get_redis()
        r.ping()
        return True, "redis connection ok"
    except redis.ConnectionError:
        return False, "redis connection failed"

port = int(os.environ.get("PORT", 8080))

def is_valid(url):
    try:
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme)
    except Exception:
        return False

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
        ERRORS.inc()
        return None

async def crawl(url, depth, current_depth=0, visited=None):
    start_time = time.time()
    REQUESTS.inc()
    
    if visited is None:
        visited = set()
    if current_depth > depth or url in visited:
        return {}

    visited.add(url)
    result = {url: [], 'depth': current_depth}
    
    try:
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
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if not isinstance(res, Exception):
                    result.update(res)
    except Exception as e:
        logger.error(f"Error crawling {url}: {str(e)}")
        ERRORS.inc()
    finally:
        CRAWL_TIME.observe(time.time() - start_time)
    
    return result

app = Flask(__name__)

# Initialize health check
health = HealthCheck()
health.add_check(redis_available)
app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())

# Prometheus metrics endpoint
app.add_url_rule('/metrics', 'metrics', view_func=lambda: prometheus_client.generate_latest())

api = Api(app, version='1.0', 
         title='rohiitgit - Web Crawler API', 
         description='A production-grade web crawler API with monitoring and documentation',
         doc='/swagger')

ns = api.namespace('api', 'Web Crawler API Documentation')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per day", "50 per hour"],
    storage_uri=f'redis://{REDIS_HOST}:{REDIS_PORT}'
)

crawler_input = api.model('CrawlerInput', {
    'url': fields.String(required=True, description='The URL to crawl'),
    'depth': fields.Integer(required=True, description='The depth of the crawl', default=1, min=1)
})

crawler_response = api.model('CrawlerResponse', {
    'results': fields.Raw(description='The crawled URLs and their links'),
    'status': fields.String(description='Status of the crawl'),
    'execution_time': fields.Float(description='Time taken to execute the crawl')
})

@ns.route('/crawl')
class CrawlAPI(Resource):
    @limiter.limit("10 per minute")
    @ns.expect(crawler_input)
    @ns.marshal_with(crawler_response)
    @ns.doc(responses={
        200: 'Success',
        400: 'Invalid input',
        429: 'Too many requests',
        500: 'Server error'
    })
    def post(self):
        """
        Crawl a website to the specified depth
        
        Returns crawled URLs and their links in a tree structure
        """
        start_time = time.time()
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
            
            execution_time = time.time() - start_time
            return {
                'results': results,
                'status': 'success',
                'execution_time': execution_time
            }
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            ERRORS.inc()
            api.abort(500, f"An error occurred: {str(e)}")

# Background task to check system health
def check_system_health():
    logger.info("Performing system health check...")
    redis_status, _ = redis_available()
    if not redis_status:
        logger.error("Redis connection failed during health check")

scheduler = BackgroundScheduler()
scheduler.add_job(check_system_health, 'interval', minutes=5)
scheduler.start()

# Test cases
class TestCrawler(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        
    def test_valid_url(self):
        response = self.app.post('/api/crawl',
                               json={'url': 'http://example.com', 'depth': 1})
        self.assertEqual(response.status_code, 200)
        
    def test_invalid_url(self):
        response = self.app.post('/api/crawl',
                               json={'url': 'invalid-url', 'depth': 1})
        self.assertEqual(response.status_code, 400)
        
    def test_invalid_depth(self):
        response = self.app.post('/api/crawl',
                               json={'url': 'http://example.com', 'depth': 0})
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    # Run tests if in test mode
    if os.environ.get('FLASK_ENV') == 'test':
        unittest.main()
    else:
        # Start the application
        from waitress import serve
        serve(app, host='0.0.0.0', port=port)
