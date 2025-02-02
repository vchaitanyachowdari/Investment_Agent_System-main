import os
import sys
import json
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from tools.openrouter_config import get_chat_completion, logger as api_logger
import logging
import time
import pandas as pd

# 设置日志记录
# logging.basicConfig(level=logging.INFO,
#                     format='%(asctime)s - %(levelname)s - %(message)s',
#                     handlers=[
#                         logging.FileHandler('logs/news_crawler.log'),
#                         logging.StreamHandler()
#                     ])
logger = logging.getLogger(__name__)


def fetch_article_content(url: str) -> str:
    """Fetch article content from URL using BeautifulSoup

    Args:
        url (str): Article URL

    Returns:
        str: Article content or empty string if failed
    """
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            # Get text content
            text = soup.get_text()
            # Break into lines and remove leading/trailing space
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip()
                      for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = ' '.join(chunk for chunk in chunks if chunk)
            return text[:5000]  # Limit content length
        return ""
    except Exception as e:
        logger.error(f"Failed to fetch article content: {e}")
        return ""


def get_stock_news(symbol: str, date: str = None, max_news: int = 10) -> list:
    """Get and process stock news from Alpha Vantage

    Args:
        symbol (str): Stock symbol, e.g. "AAPL"
        date (str, optional): The date to get news up to (YYYY-MM-DD). If None, uses current date.
        max_news (int, optional): Maximum number of news articles to fetch. Defaults to 10.

    Returns:
        list: List of news articles, each containing title, content, publish time etc.
    """
    # Limit max news to 100
    max_news = min(max_news, 100)

    # Get current date if date not provided
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Build news file path
    news_dir = os.path.join("src", "data", "stock_news", symbol)
    logger.info(f"News directory: {news_dir}")

    # Ensure directory exists
    try:
        os.makedirs(news_dir, exist_ok=True)
        logger.info(
            f"Successfully created or confirmed directory exists: {news_dir}")
    except Exception as e:
        logger.error(f"Failed to create directory: {e}")
        return []

    news_file = os.path.join(news_dir, f"{date}_news.json")
    logger.info(f"News file path: {news_file}")

    # Check if we need to update news
    if os.path.exists(news_file):
        try:
            with open(news_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cached_news = data.get("news", [])
                if len(cached_news) >= max_news:
                    logger.info(f"Using cached news data: {news_file}")
                    return cached_news[:max_news]
                else:
                    logger.info(
                        f"Cached news count({len(cached_news)}) is less than requested({max_news})")
        except Exception as e:
            logger.error(f"Failed to read cache file: {e}")

    logger.info(f'Starting to fetch news for {symbol} up to {date}...')

    try:
        # Convert date to required format YYYYMMDDTHHMM
        target_date = datetime.strptime(date, "%Y-%m-%d")
        date_str = target_date.strftime("%Y%m%dT0000")
        next_date = (target_date + timedelta(days=1)).strftime("%Y%m%dT0000")

        # Get news from Alpha Vantage
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&time_from={date_str}&time_to={next_date}&limit={max_news}&apikey={api_key}'

        response = requests.get(url)
        data = response.json()

        if "feed" not in data:
            logger.warning(f"No news found for {symbol}")
            return []

        news_data = data["feed"]
        logger.info(f"Raw news count: {len(news_data)}")
        if news_data:
            logger.info(
                f"First raw news item:\n{json.dumps(news_data[0], indent=2)}")

        # Process news
        news_list = []
        for i, news in enumerate(news_data[:max_news]):
            try:
                # Extract data from Alpha Vantage response
                title = news.get('title', '')
                content = news.get('summary', '')
                source = news.get('source', '')
                url = news.get('url', '')
                time_published = news.get('time_published', '')

                # Convert timestamp from format YYYYMMDDTHHMMSS to datetime
                try:
                    publish_time = datetime.strptime(
                        time_published, "%Y%m%dT%H%M%S")
                    publish_time_str = publish_time.strftime(
                        '%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.warning(
                        f"Failed to parse publish time: {time_published}, error: {e}")
                    continue

                # Log processing details
                logger.info(f"\nProcessing news item {i+1}:")
                logger.info(f"Title: {title}")
                logger.info(f"Content length: {len(content)}")
                logger.info(f"Source: {source}")
                logger.info(f"URL: {url}")
                logger.info(f"Publish time: {publish_time_str}")

                # Filter logic
                if not title and not content:
                    logger.warning(
                        "Skipping: both title and content are empty")
                    continue

                if len(content) < 10 and len(title) < 10:
                    logger.warning(
                        "Skipping: both title and content are too short")
                    continue

                # If content is too short, try to fetch full article
                if len(content) < 100:
                    full_content = fetch_article_content(url)
                    if full_content:
                        content = full_content

                # Add news item
                news_item = {
                    "title": title.strip(),
                    "content": content.strip() if content else title.strip(),
                    "publish_time": publish_time_str,
                    "source": source.strip(),
                    "url": url.strip(),
                }
                news_list.append(news_item)
                logger.info(f"Successfully added news: {news_item['title']}")

            except Exception as e:
                logger.error(f"Failed to process single news item: {e}")
                continue

        # Sort by publish time
        news_list.sort(key=lambda x: x["publish_time"], reverse=True)

        # Keep only requested number of news
        news_list = news_list[:max_news]

        # Save to file
        try:
            save_data = {
                "date": date,
                "news": news_list
            }
            with open(news_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            logger.info(
                f"Successfully saved {len(news_list)} news items to file: {news_file}")

            # # Also save to combined news file
            # combined_news_file = os.path.join(
            #     "src", "data", "stock_news", f"{symbol}_news.json")
            # with open(combined_news_file, 'w', encoding='utf-8') as f:
            #     json.dump(save_data, f, ensure_ascii=False, indent=2)
            # logger.info(
            #     f"Successfully saved to combined news file: {combined_news_file}")

        except Exception as e:
            logger.error(f"Failed to save news data to file: {e}")

        return news_list

    except Exception as e:
        logger.error(f"Failed to fetch news data: {e}")
        return []


def get_news_sentiment(news_list: list, date: str = None, num_of_news: int = 5) -> float:
    """Analyze news sentiment using LLM

    Args:
        news_list (list): List of news articles
        date (str, optional): The date for sentiment analysis (YYYY-MM-DD). If None, uses current date.
        num_of_news (int, optional): Number of news articles to analyze. Defaults to 5.

    Returns:
        float: Sentiment score between -1 and 1
    """
    if not news_list:
        return 0.0

    # Get current date if date not provided
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # Check cache
    cache_file = "src/data/sentiment_cache.json"
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)

    # Check cache using just the date as key
    if os.path.exists(cache_file):
        logger.info("Found sentiment analysis cache file")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                if date in cache:
                    logger.info("Using cached sentiment analysis result")
                    return cache[date]
                logger.info("No matching sentiment analysis cache found")
        except Exception as e:
            logger.error(f"Failed to read sentiment cache: {e}")
            cache = {}
    else:
        logger.info(
            "No sentiment analysis cache file found, will create new one")
        cache = {}

    # Prepare system message
    system_message = {
        "role": "system",
        "content": """You are a professional US stock market analyst specializing in news sentiment analysis. You need to analyze a set of news articles and provide a sentiment score between -1 and 1:
        - 1 represents extremely positive (e.g., major positive news, breakthrough earnings, strong industry support)
        - 0.5 to 0.9 represents positive (e.g., growth in earnings, new project launch, contract wins)
        - 0.1 to 0.4 represents slightly positive (e.g., small contract signings, normal operations)
        - 0 represents neutral (e.g., routine announcements, personnel changes, non-impactful news)
        - -0.1 to -0.4 represents slightly negative (e.g., minor litigation, non-core business losses)
        - -0.5 to -0.9 represents negative (e.g., declining performance, major customer loss, industry regulation tightening)
        - -1 represents extremely negative (e.g., major violations, core business severe losses, regulatory penalties)

        Focus on:
        1. Performance related: financial reports, earnings forecasts, revenue/profit
        2. Policy impact: industry policies, regulatory policies, local policies
        3. Market performance: market share, competitive position, business model
        4. Capital operations: M&A, equity incentives, additional issuance
        5. Risk events: litigation, arbitration, penalties
        6. Industry position: technological innovation, patents, market share
        7. Public opinion: media evaluation, social impact

        Please ensure to analyze:
        1. News authenticity and reliability
        2. News timeliness and impact scope
        3. Actual impact on company fundamentals
        4. US stock market's specific reaction patterns"""
    }

    # Prepare news content
    news_content = "\n\n".join([
        f"Title: {news['title']}\n"
        f"Source: {news['source']}\n"
        f"Time: {news['publish_time']}\n"
        f"Content: {news['content']}"
        for news in news_list[:num_of_news]
    ])

    user_message = {
        "role": "user",
        "content": f"Please analyze the sentiment of the following US stock related news:\n\n{news_content}\n\nPlease return only a number between -1 and 1, no explanation needed."
    }

    try:
        # Get LLM analysis result
        result = get_chat_completion([system_message, user_message])
        if result is None:
            logger.error("Error: LLM returned None")
            return 0.0

        # Extract numeric result
        try:
            sentiment_score = float(result.strip())
        except ValueError as e:
            logger.error(f"Error parsing sentiment score: {e}")
            logger.error(f"Raw result: {result}")
            return 0.0

        # Ensure score is between -1 and 1
        sentiment_score = max(-1.0, min(1.0, sentiment_score))

        # Cache result using date as key
        cache[date] = sentiment_score
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            logger.info(
                f"Successfully cached sentiment score {sentiment_score} for date {date}")
        except Exception as e:
            logger.error(f"Error writing cache: {e}")

        return sentiment_score

    except Exception as e:
        logger.error(f"Error analyzing news sentiment: {e}")
        return 0.0  # Return neutral score on error
