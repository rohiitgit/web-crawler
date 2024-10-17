# Web Crawler API

## HOSTED at

``` https://web-crawler-gnwr.onrender.com/api/crawl ```

## Overview
This project implements a simple web crawler that can be triggered via an API call. It accepts a starting URL and a specified depth for crawling, returning a structured JSON response with the crawled links.

## Run and Test API locally
```
git clone https://github.com/rohiitgit/web-crawler.git
cd web-crawler
pip install -r requirements.txt
python api.py
```

## Features
- Crawl web pages to a specified depth.
- Return crawled links in a structured JSON format.
- Handle basic HTTP request exceptions.
- Validate input URL and depth.

## API Endpoint

### POST /api/crawl

**Description**: Initiates the crawling process from the given URL up to the specified depth.

#### Request

- **Headers**:
  - `Content-Type: application/json`

- **Body**:
    ```json
    {
      "root_url": "https://example.com",
      "depth": 2
    }
    ```

#### Parameters
- **root_url** (string, required): The starting webpage URL. Must be a valid URL format (e.g., `https://` or `http://`).
- **depth** (integer, required): The maximum depth to which the crawler should explore links. Must be a non-negative integer.

#### Response

**Success (200 OK)**:
```json
{
  "status": "success",
  "data": {
    "crawled_links": [
      {
        "url": "https://example.com",
        "depth": 0
      },
      {
        "url": "https://example.com/page1",
        "depth": 1
      },
      ...
    ],
    "total_links_crawled": 4
  }
}
