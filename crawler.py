import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def is_valid(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def crawl(url, depth, current_depth=0, visited=None):
    if visited is None:
        visited = set()

    if current_depth > depth or url in visited:
        return {}

    visited.add(url)
    result = {url: []}

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.find_all('a'):
            href = link.get('href')
            if href:
                full_url = urljoin(url, href)
                if is_valid(full_url):
                    result[url].append(full_url)
                    if current_depth < depth:
                        print(f'Crawling {full_url}...')
                        result.update(crawl(full_url, depth, current_depth + 1, visited))

    except requests.RequestException:
        print('Error crawling URL:', url)
        print('Continuing with other links...')

    return result

