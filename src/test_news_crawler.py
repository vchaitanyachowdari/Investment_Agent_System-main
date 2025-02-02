import os
import sys
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import argparse
import requests
from tools.news_crawler import get_stock_news
import logging

# 设置日志记录
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_alpha_vantage_news(ticker, target_date, num_of_news):
    """Test the Alpha Vantage news API for a specific date"""
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')

    # Convert date to required format YYYYMMDDTHHMM
    date_str = target_date.strftime("%Y%m%dT0000")
    next_date = (target_date + timedelta(days=1)).strftime("%Y%m%dT0000")

    url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&time_from={date_str}&time_to={next_date}&limit={num_of_news}&apikey={api_key}'

    try:
        response = requests.get(url)
        data = response.json()

        if "feed" in data:
            articles = data["feed"]
            print(
                f"\nFound {len(articles)} articles for {target_date.strftime('%Y-%m-%d')}")

            for i, article in enumerate(articles, 1):
                print(f"\n{i}. {article.get('title', 'No title')}")
                print(f"   Source: {article.get('source', 'Unknown')}")
                print(f"   Time: {article.get('time_published', 'Unknown')}")
                print(f"   URL: {article.get('url', 'No URL')}")
                print(
                    f"   Summary: {article.get('summary', 'No summary')[:200]}...")

                # Print sentiment if available
                if "overall_sentiment_score" in article:
                    print(
                        f"   Sentiment Score: {article['overall_sentiment_score']}")
        else:
            print(f"No articles found for {target_date.strftime('%Y-%m-%d')}")

    except Exception as e:
        print(f"Error fetching news: {str(e)}")


def test_news_crawler(symbol: str = "AAPL", date: str = None):
    """Test the news crawler functionality with Alpha Vantage API

    Args:
        symbol (str, optional): Stock symbol. Defaults to "AAPL".
        date (str, optional): Date to test (YYYY-MM-DD). Defaults to None.
    """
    # Load environment variables
    load_dotenv()

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"\nTesting news crawler for {symbol} on {date}")
    logger.info("-" * 50)

    # Test with different numbers of news
    for num_news in [5, 10]:
        logger.info(f"\nTesting with {num_news} news articles:")
        news_list = get_stock_news(symbol, date, num_news)

        if news_list:
            logger.info(
                f"Successfully retrieved {len(news_list)} news articles")
            # Print details of first article
            first_news = news_list[0]
            logger.info("\nFirst news article details:")
            logger.info(f"Title: {first_news['title']}")
            logger.info(f"Source: {first_news['source']}")
            logger.info(f"Published: {first_news['publish_time']}")
            logger.info(f"URL: {first_news['url']}")
            logger.info(f"Content length: {len(first_news['content'])}")
        else:
            logger.warning("No news articles found")

    # Test with a past date
    past_date = (datetime.strptime(date, "%Y-%m-%d") -
                 timedelta(days=7)).strftime("%Y-%m-%d")
    logger.info(f"\nTesting with past date {past_date}:")
    news_list = get_stock_news(symbol, past_date, 5)
    if news_list:
        logger.info(
            f"Successfully retrieved {len(news_list)} news articles for past date")
    else:
        logger.warning("No news articles found for past date")


if __name__ == "__main__":
    # Test current date
    test_news_crawler()

    # Test specific dates
    test_dates = [
        "2023-11-24",  # Past date
        "2024-11-20",  # Future date
        "2023-11-20",  # Another past date
    ]

    for test_date in test_dates:
        test_news_crawler(date=test_date)
