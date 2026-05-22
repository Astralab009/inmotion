import logging
import os
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
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 12
MAX_ITEMS_PER_SOURCE = 30

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

NewsItem = Dict[str, Any]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("news_crawler")


def fetch_url(url: str, *, params: Optional[dict] = None) -> requests.Response:
    response = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
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
    """Fetch Sina Finance RSS first, then fall back to finance page HTML."""
    rss_candidates = [
        "https://rss.sina.com.cn/finance/roll.xml",
        "https://rss.sina.com.cn/finance/focus.xml",
        "https://rss.sina.com.cn/finance/stock/usstock.xml",
    ]
    for rss_url in rss_candidates:
        try:
            items = parse_rss(rss_url, "sina")
            if items:
                return dedupe_items(items)
        except Exception as exc:
            logger.warning("sina RSS attempt failed for %s: %s", rss_url, exc)

    html_url = "https://finance.sina.com.cn/stock/usstock/c/"
    response = fetch_url(html_url)
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    for link in soup.select("a[href]")[:300]:
        href = link.get("href", "")
        title = clean_text(link.get_text(" ", strip=True))
        if len(title) < 6 or "finance.sina.com.cn" not in href:
            continue
        item = normalize_item(
            title=title,
            summary="",
            content=title,
            source="sina",
            url=href,
            published_at=None,
            base_url=html_url,
        )
        if item:
            items.append(item)
    return dedupe_items(items)[:MAX_ITEMS_PER_SOURCE]


def crawl_eastmoney() -> List[NewsItem]:
    """Fetch Eastmoney 7x24 flash news from common JSON endpoints."""
    attempts = [
        (
            "https://zhibo.eastmoney.com/api/qt/timeline",
            {"limit": MAX_ITEMS_PER_SOURCE},
        ),
        (
            "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html",
            {},
        ),
    ]

    for url, params in attempts:
        try:
            text = fetch_url(url, params=params).text.strip()
            text = re.sub(r"^[^(]*\((.*)\)\s*;?$", r"\1", text, flags=re.S)
            payload = requests.models.complexjson.loads(text)
            data = payload.get("data") or payload.get("Data") or payload
            records = data.get("list") if isinstance(data, dict) else data
            if isinstance(records, dict):
                records = records.get("items") or records.get("List") or []
            if not isinstance(records, list):
                records = []

            items = []
            for record in records[:MAX_ITEMS_PER_SOURCE]:
                title = (
                    record.get("title")
                    or record.get("Title")
                    or record.get("content")
                    or record.get("Content")
                )
                url_value = (
                    record.get("url")
                    or record.get("Url")
                    or record.get("link")
                    or record.get("Link")
                    or f"https://zhibo.eastmoney.com/news/{record.get('id') or record.get('newsid', '')}"
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
                    base_url="https://zhibo.eastmoney.com",
                )
                if item:
                    items.append(item)
            if items:
                return dedupe_items(items)
        except Exception as exc:
            logger.warning("eastmoney API attempt failed for %s: %s", url, exc)

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
