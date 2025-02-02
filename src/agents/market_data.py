from langchain_core.messages import HumanMessage
from tools.openrouter_config import get_chat_completion
from agents.state import AgentState
from tools.api import get_financial_metrics, get_financial_statements, get_insider_trades, get_market_data, get_price_history

from datetime import datetime, timedelta


def market_data_agent(state: AgentState):
    """Responsible for gathering and preprocessing market data"""
    messages = state["messages"]
    data = state["data"]

    # Get current_date from state
    current_date = data.get("current_date") or data["end_date"]

    # 确保至少有一年的历史数据用于技术分析
    current_date_obj = datetime.strptime(current_date, '%Y-%m-%d')
    min_start_date = (current_date_obj - timedelta(days=365)
                      ).strftime('%Y-%m-%d')

    # 使用原始的start_date和min_start_date中较早的那个
    original_start_date = data["start_date"]
    start_date = min(original_start_date,
                     min_start_date) if original_start_date else min_start_date

    # Get all required data
    ticker = data["ticker"]

    # 获取从start_date到current_date的所有数据
    prices = get_price_history(ticker, start_date, current_date)

    # 获取当前日期的财务和市场数据
    financial_metrics = get_financial_metrics(ticker)
    financial_line_items = get_financial_statements(ticker)
    insider_trades = get_insider_trades(ticker)
    market_data = get_market_data(ticker)

    return {
        "messages": messages,
        "data": {
            **data,
            "prices": prices,
            "start_date": start_date,
            "end_date": current_date,
            "current_date": current_date,
            "financial_metrics": financial_metrics,
            "financial_line_items": financial_line_items,
            "insider_trades": insider_trades,
            "market_cap": market_data["market_cap"],
            "market_data": market_data,
        }
    }
