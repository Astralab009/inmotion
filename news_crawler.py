import logging
import os
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin

import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 12
MAX_ITEMS_PER_SOURCE = 30

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
}

NewsItem = Dict[str, Any]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("news_crawler")


def fetch_url(
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    session: Optional[requests.Session] = None,
) -> requests.Response:
    request_headers = {**HEADERS, **(headers or {})}
    client = session or requests
    response = client.get(
        url,
        headers=request_headers,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response


def parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            return parse_datetime(int(text))

        dt = None
        for candidate in (text, text.replace("Z", "+00:00")):
            try:
                dt = datetime.fromisoformat(candidate)
                break
            except ValueError:
                pass

        if dt is None:
            try:
                dt = parsedate_to_datetime(text)
            except (TypeError, ValueError):
                return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def parse_json_or_jsonp(text: str) -> Any:
    payload = text.strip().lstrip("\ufeff")
    assignment_match = re.match(r"^(?:var\s+)?[\w$]+\s*=\s*(.*?);?$", payload, flags=re.S)
    if assignment_match:
        payload = assignment_match.group(1).strip()

    jsonp_match = re.match(r"^[\w$.]+\((.*)\)\s*;?$", payload, flags=re.S)
    if jsonp_match:
        payload = jsonp_match.group(1).strip()

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        object_start = payload.find("{")
        object_end = payload.rfind("}")
        if object_start != -1 and object_end != -1 and object_end > object_start:
            return json.loads(payload[object_start : object_end + 1])

        array_start = payload.find("[")
        array_end = payload.rfind("]")
        if array_start != -1 and array_end != -1 and array_end > array_start:
            return json.loads(payload[array_start : array_end + 1])
        raise


def normalize_url(url: str, base_url: str) -> str:
    return urljoin(base_url, url.strip()) if url else ""


def normalize_item(
    *,
    title: Any,
    summary: Any = "",
    content: Any = "",
    source: str,
    url: str,
    published_at: Any = None,
    base_url: str = "",
) -> Optional[NewsItem]:
    normalized_title = clean_text(title)
    normalized_url = normalize_url(url, base_url)
    if not normalized_title or not normalized_url:
        return None

    normalized_content = clean_text(content) or clean_text(summary) or normalized_title
    return {
        "title": normalized_title,
        "summary": clean_text(summary)[:1000],
        "content": normalized_content,
        "source": source,
        "url": normalized_url,
        "published_at": parse_datetime(published_at) or datetime.now(timezone.utc),
    }


def dedupe_items(items: Iterable[NewsItem]) -> List[NewsItem]:
    seen = set()
    deduped = []
    for item in items:
        url = item["url"]
        if url in seen:
            continue
        seen.add(url)
        deduped.append(item)
    return deduped


def safe_crawl(name: str, crawler) -> List[NewsItem]:
    try:
        items = crawler()
        logger.info("%s fetched %s item(s)", name, len(items))
        return items
    except Exception:
        logger.exception("%s crawl failed", name)
        return []


def parse_rss(url: str, source: str, limit: int = MAX_ITEMS_PER_SOURCE) -> List[NewsItem]:
    response = fetch_url(url)
    soup = BeautifulSoup(response.content, "html.parser")
    items = []
    for entry in soup.find_all("item")[:limit]:
        title_tag = entry.find("title")
        link_tag = entry.find("link")
        description_tag = entry.find("description")
        pub_date_tag = entry.find("pubDate") or entry.find("pubdate")
        link = clean_text(link_tag.text if link_tag else "")
        item = normalize_item(
            title=title_tag.text if title_tag else "",
            summary=description_tag.text if description_tag else "",
            content=description_tag.text if description_tag else "",
            source=source,
            url=link,
            published_at=pub_date_tag.text if pub_date_tag else None,
            base_url=url,
        )
        if item:
            items.append(item)
    return items


def crawl_wallstreetcn() -> List[NewsItem]:
    """Fetch Wallstreetcn global/macro news, falling back to HTML parsing."""
    api_attempts = [
        (
            "https://api-one-wscn.awtmt.com/apiv1/content/articles",
            {"channel": "global", "limit": MAX_ITEMS_PER_SOURCE},
        ),
        (
            "https://api-one-wscn.awtmt.com/apiv1/content/lives",
            {"channel": "global-channel", "limit": MAX_ITEMS_PER_SOURCE},
        ),
    ]

    for url, params in api_attempts:
        try:
            payload = fetch_url(url, params=params).json()
            data = payload.get("data", {})
            records = data.get("items") or data.get("articles") or data.get("lives") or []
            items = []
            for record in records[:MAX_ITEMS_PER_SOURCE]:
                article = record.get("resource") if isinstance(record.get("resource"), dict) else record
                article_id = article.get("id") or article.get("uri")
                article_url = article.get("url") or (
                    f"https://wallstreetcn.com/articles/{article_id}" if article_id else ""
                )
                item = normalize_item(
                    title=article.get("title") or article.get("content_text") or article.get("content"),
                    summary=article.get("summary") or article.get("description") or article.get("content_short"),
                    content=article.get("content") or article.get("content_text") or article.get("summary"),
                    source="wallstreetcn",
                    url=article_url,
                    published_at=article.get("display_time")
                    or article.get("created_at")
                    or article.get("updated_at"),
                    base_url="https://wallstreetcn.com",
                )
                if item:
                    items.append(item)
            if items:
                return dedupe_items(items)
        except Exception as exc:
            logger.warning("wallstreetcn API attempt failed: %s", exc)

    response = fetch_url("https://wallstreetcn.com/news/global")
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    for link in soup.select('a[href*="/articles/"], a[href*="/news/"]')[:MAX_ITEMS_PER_SOURCE * 2]:
        title = clean_text(link.get_text(" ", strip=True))
        href = link.get("href", "")
        if len(title) < 6:
            continue
        item = normalize_item(
            title=title,
            summary="",
            content=title,
            source="wallstreetcn",
            url=href,
            published_at=None,
            base_url="https://wallstreetcn.com",
        )
        if item:
            items.append(item)
    return dedupe_items(items)[:MAX_ITEMS_PER_SOURCE]


def crawl_sina() -> List[NewsItem]:
    """Fetch Sina Finance from RSS/API endpoints without scraping blocked pages."""
    sina_headers = {
        "Referer": "https://finance.sina.com.cn/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    }
    rss_candidates = [
        "https://rss.sina.com.cn/finance/focus.xml",
        "http://rss.sina.com.cn/finance/focus.xml",
        "https://rss.sina.com.cn/finance/roll.xml",
        "http://rss.sina.com.cn/finance/roll.xml",
        "https://rss.sina.com.cn/roll/finance/hot_roll.xml",
        "http://rss.sina.com.cn/roll/finance/hot_roll.xml",
    ]
    for rss_url in rss_candidates:
        try:
            response = fetch_url(rss_url, headers=sina_headers)
            soup = BeautifulSoup(response.content, "html.parser")
            items = []
            for entry in soup.find_all("item")[:MAX_ITEMS_PER_SOURCE]:
                title_tag = entry.find("title")
                link_tag = entry.find("link")
                description_tag = entry.find("description")
                pub_date_tag = entry.find("pubDate") or entry.find("pubdate")
                item = normalize_item(
                    title=title_tag.text if title_tag else "",
                    summary=description_tag.text if description_tag else "",
                    content=description_tag.text if description_tag else "",
                    source="sina",
                    url=clean_text(link_tag.text if link_tag else ""),
                    published_at=pub_date_tag.text if pub_date_tag else None,
                    base_url=rss_url,
                )
                if item:
                    items.append(item)
            if items:
                return dedupe_items(items)
        except Exception as exc:
            logger.warning("sina RSS attempt failed for %s: %s", rss_url, exc)

    api_attempts = [
        (
            "https://feed.mix.sina.com.cn/api/roll/get",
            {"pageid": 153, "lid": 2509, "k": "", "num": 50, "page": 1},
        ),
        (
            "https://feed.mix.sina.com.cn/api/roll/get",
            {"pageid": 153, "lid": 2510, "k": "", "num": 50, "page": 1},
        ),
        (
            "https://feed.mix.sina.com.cn/api/roll/get",
            {"pageid": 153, "lid": 1686, "k": "", "num": 50, "page": 1},
        ),
    ]

    session = requests.Session()
    try:
        fetch_url("https://finance.sina.com.cn/", headers=sina_headers, session=session)
    except Exception as exc:
        logger.warning("sina session warm-up failed: %s", exc)

    for api_url, params in api_attempts:
        try:
            response = fetch_url(api_url, params=params, headers=sina_headers, session=session)
            payload = parse_json_or_jsonp(response.text)
            result = payload.get("result", payload) if isinstance(payload, dict) else {}
            records = result.get("data") or payload.get("data") or []
            if isinstance(records, dict):
                records = records.get("list") or records.get("items") or []
            if not isinstance(records, list):
                records = []

            items = []
            for record in records[:MAX_ITEMS_PER_SOURCE]:
                title = record.get("title") or record.get("stitle")
                url = record.get("url") or record.get("wapurl") or record.get("link")
                summary = record.get("intro") or record.get("summary") or ""
                published_at = (
                    record.get("ctime")
                    or record.get("time")
                    or record.get("create_time")
                    or record.get("date")
                )
                item = normalize_item(
                    title=title,
                    summary=summary,
                    content=summary or title,
                    source="sina",
                    url=url,
                    published_at=published_at,
                    base_url="https://finance.sina.com.cn/",
                )
                if item:
                    items.append(item)
            if items:
                return dedupe_items(items)
        except Exception as exc:
            logger.warning("sina API attempt failed for %s: %s", api_url, exc)

    return []


def crawl_eastmoney() -> List[NewsItem]:
    """Fetch Eastmoney flash news from JSON/JSONP endpoints, with HTML fallback."""
    eastmoney_headers = {
        "Referer": "https://www.eastmoney.com/",
        "Accept": "application/json,text/javascript,text/html,application/xhtml+xml,*/*;q=0.8",
    }
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    session = requests.Session()
    try:
        fetch_url("https://www.eastmoney.com/", headers=eastmoney_headers, session=session)
        fetch_url("https://kuaixun.eastmoney.com/", headers=eastmoney_headers, session=session)
    except Exception as exc:
        logger.warning("eastmoney session warm-up failed: %s", exc)

    api_attempts = [
        (
            "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html",
            {},
        ),
        (
            "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html",
            {"_": now_ms},
        ),
        (
            "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns",
            {
                "client": "web",
                "biz": "web_news_col",
                "column": "724",
                "order": 1,
                "needInteractData": 0,
                "page_index": 1,
                "page_size": 50,
                "req_trace": now_ms,
            },
        ),
        (
            "https://zhibo.eastmoney.com/api/qt/timeline",
            {"limit": MAX_ITEMS_PER_SOURCE, "_": now_ms},
        )
    ]

    def extract_eastmoney_records(payload: Any) -> List[dict]:
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        if not isinstance(payload, dict):
            return []

        candidates = [
            payload.get("data"),
            payload.get("Data"),
            payload.get("LivesList"),
            payload.get("news"),
            payload,
        ]
        for candidate in candidates:
            if isinstance(candidate, list):
                return [record for record in candidate if isinstance(record, dict)]
            if isinstance(candidate, dict):
                for key in ("list", "List", "items", "Items", "news", "LivesList", "data"):
                    value = candidate.get(key)
                    if isinstance(value, list):
                        return [record for record in value if isinstance(record, dict)]
        return []

    for url, params in api_attempts:
        try:
            response = fetch_url(url, params=params, headers=eastmoney_headers, session=session)
            payload = parse_json_or_jsonp(response.text)
            records = extract_eastmoney_records(payload)

            items = []
            for record in records[:MAX_ITEMS_PER_SOURCE]:
                title = (
                    record.get("title")
                    or record.get("Title")
                    or record.get("content")
                    or record.get("Content")
                    or record.get("digest")
                    or record.get("Digest")
                )
                url_value = (
                    record.get("url")
                    or record.get("Url")
                    or record.get("link")
                    or record.get("Link")
                    or record.get("newsUrl")
                    or record.get("NewsUrl")
                    or f"https://kuaixun.eastmoney.com/{record.get('id') or record.get('newsid') or ''}"
                )
                item = normalize_item(
                    title=title,
                    summary=record.get("digest") or record.get("Digest") or "",
                    content=record.get("content") or record.get("Content") or title,
                    source="eastmoney",
                    url=url_value,
                    published_at=record.get("showtime")
                    or record.get("ShowTime")
                    or record.get("time")
                    or record.get("Time")
                    or record.get("sort_time"),
                    base_url="https://kuaixun.eastmoney.com/",
                )
                if item:
                    items.append(item)
            if items:
                return dedupe_items(items)
        except Exception as exc:
            logger.warning("eastmoney API attempt failed for %s: %s", url, exc)

    html_attempts = [
        "https://wap.eastmoney.com/kuaixun/index.html",
        "https://kuaixun.eastmoney.com/",
    ]
    for html_url in html_attempts:
        try:
            response = fetch_url(html_url, headers=eastmoney_headers, session=session)
            response.encoding = response.apparent_encoding or response.encoding
            soup = BeautifulSoup(response.text, "html.parser")
            items = []
            for link in soup.select("a[href]")[:300]:
                title = clean_text(link.get_text(" ", strip=True))
                href = link.get("href", "")
                if len(title) < 6:
                    continue
                if "eastmoney.com" not in href and not href.startswith(("/", "./")):
                    continue
                item = normalize_item(
                    title=title,
                    summary="",
                    content=title,
                    source="eastmoney",
                    url=href,
                    published_at=None,
                    base_url=html_url,
                )
                if item:
                    items.append(item)
            if items:
                return dedupe_items(items)[:MAX_ITEMS_PER_SOURCE]
        except Exception as exc:
            logger.warning("eastmoney HTML attempt failed for %s: %s", html_url, exc)

    return []


def crawl_cls() -> List[NewsItem]:
    """Fetch Cailianpress telegraph/flash news from its web JSON endpoint."""
    attempts = [
        (
            "https://www.cls.cn/nodeapi/telegraphList",
            {"app": "CailianpressWeb", "os": "web", "sv": "8.0.0"},
        ),
        (
            "https://www.cls.cn/api/sw",
            {"app": "CailianpressWeb", "os": "web", "sv": "8.0.0"},
        ),
    ]

    for url, params in attempts:
        try:
            payload = fetch_url(url, params=params).json()
            data = payload.get("data") or payload
            records = (
                data.get("roll_data")
                or data.get("telegraph_list")
                or data.get("list")
                or data.get("items")
                or []
            )
            if isinstance(records, dict):
                records = records.get("list") or records.get("items") or []

            items = []
            for record in records[:MAX_ITEMS_PER_SOURCE]:
                article_id = record.get("id") or record.get("article_id")
                item = normalize_item(
                    title=record.get("title") or record.get("content"),
                    summary=record.get("brief") or record.get("summary") or "",
                    content=record.get("content") or record.get("title"),
                    source="cls",
                    url=record.get("shareurl")
                    or record.get("url")
                    or (f"https://www.cls.cn/detail/{article_id}" if article_id else ""),
                    published_at=record.get("ctime")
                    or record.get("time")
                    or record.get("published_at"),
                    base_url="https://www.cls.cn",
                )
                if item:
                    items.append(item)
            if items:
                return dedupe_items(items)
        except Exception as exc:
            logger.warning("cls API attempt failed for %s: %s", url, exc)

    return []


def insert_news(conn, items: Sequence[NewsItem]) -> List[Tuple[str, str, str, str]]:
    if not items:
        return []

    deduped_items = dedupe_items(items)
    urls = [item["url"] for item in deduped_items]

    with conn.cursor() as cur:
        cur.execute("SELECT url FROM news WHERE url = ANY(%s)", (urls,))
        existing_urls = {row[0] for row in cur.fetchall()}

        new_items = [item for item in deduped_items if item["url"] not in existing_urls]
        if not new_items:
            logger.info("inserted 0 new news item(s)")
            return []

        values = [
            (
                item["title"],
                item["summary"],
                item["content"],
                item["source"],
                item["url"],
                item["published_at"],
            )
            for item in new_items
        ]

        cur.executemany(
            """
            INSERT INTO news (title, summary, content, source, url, published_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            values,
        )

        inserted_urls = [item["url"] for item in new_items]
        cur.execute(
            """
            SELECT id::text, title, content, url
            FROM news
            WHERE url = ANY(%s)
            """,
            (inserted_urls,),
        )
        inserted = cur.fetchall()

    logger.info("inserted %s new news item(s)", len(inserted))
    return inserted


def fetch_sectors(conn) -> List[Tuple[int, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM sectors WHERE name IS NOT NULL AND name <> ''")
        return [(sector_id, name) for sector_id, name in cur.fetchall()]


def match_news_to_sectors(conn, inserted_news: Sequence[Tuple[str, str, str, str]]) -> int:
    if not inserted_news:
        return 0

    sectors = fetch_sectors(conn)
    if not sectors:
        logger.info("no sectors found; skipping sector matching")
        return 0

    associations = set()
    for news_id, title, content, _url in inserted_news:
        haystack = f"{title or ''}\n{content or ''}".lower()
        for sector_id, sector_name in sectors:
            if sector_name.lower() in haystack:
                associations.add((news_id, sector_id))

    if not associations:
        logger.info("no sector associations matched")
        return 0

    query = """
        INSERT INTO news_sectors (news_id, sector_id)
        VALUES (%s, %s)
        ON CONFLICT (news_id, sector_id) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.executemany(query, list(associations))
        inserted_count = cur.rowcount
    logger.info("inserted %s news-sector association(s)", inserted_count)
    return inserted_count


def crawl_all_sources() -> List[NewsItem]:
    crawlers = [
        ("wallstreetcn", crawl_wallstreetcn),
        ("sina", crawl_sina),
        ("eastmoney", crawl_eastmoney),
        ("cls", crawl_cls),
    ]
    items: List[NewsItem] = []
    for name, crawler in crawlers:
        items.extend(safe_crawl(name, crawler))
    return dedupe_items(items)


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    all_items = crawl_all_sources()
    logger.info("fetched %s unique item(s) in total", len(all_items))
    if not all_items:
        return

    conn = None
    try:
        conn = psycopg2.connect(database_url)
        inserted_news = insert_news(conn, all_items)
        match_news_to_sectors(conn, inserted_news)
        conn.commit()
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
