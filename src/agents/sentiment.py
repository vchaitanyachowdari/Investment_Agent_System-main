from langchain_core.messages import HumanMessage
from agents.state import AgentState, show_agent_reasoning
from tools.news_crawler import get_stock_news, get_news_sentiment
from tools.openrouter_config import get_chat_completion
import json
from datetime import datetime, timedelta


def sentiment_agent(state: AgentState):
    """Analyzes market sentiment and generates trading signals"""
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    symbol = data["ticker"]
    current_date = data["end_date"]  # 使用回测的当前日期

    # Get number of news from command line args, default to 5
    num_of_news = data.get("num_of_news", 5)

    # Get news data and analyze sentiment using historical date
    news_list = get_stock_news(symbol, date=current_date, max_news=num_of_news)

    # Filter for news within last 7 days
    cutoff_date = datetime.strptime(
        current_date, "%Y-%m-%d") - timedelta(days=7)
    recent_news = [news for news in news_list
                   if datetime.strptime(news['publish_time'], '%Y-%m-%d %H:%M:%S') > cutoff_date]

    sentiment_score = get_news_sentiment(
        recent_news, date=current_date, num_of_news=num_of_news)

    # Generate trading signal and confidence based on sentiment score
    if sentiment_score >= 0.5:
        signal = "bullish"
        confidence = str(round(abs(sentiment_score) * 100)) + "%"
    elif sentiment_score <= -0.5:
        signal = "bearish"
        confidence = str(round(abs(sentiment_score) * 100)) + "%"
    else:
        signal = "neutral"
        confidence = str(round((1 - abs(sentiment_score)) * 100)) + "%"

    # Generate analysis results
    message_content = {
        "signal": signal,
        "confidence": confidence,
        "reasoning": f"Based on {len(recent_news)} recent news articles up to {current_date}, sentiment score: {sentiment_score:.2f}"
    }

    # Show reasoning if flag is set
    if show_reasoning:
        show_agent_reasoning(message_content, "Sentiment Analysis Agent")

    # Create message
    message = HumanMessage(
        content=json.dumps(message_content),
        name="sentiment_agent",
    )

    return {
        "messages": [message],
        "data": data,
    }
