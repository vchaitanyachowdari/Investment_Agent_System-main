from typing import Dict, Any, List
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import random
import json


def get_financial_metrics(ticker: str) -> Dict[str, Any]:
    """获取财务指标数据，包含缓存机制和时间戳"""
    stock = yf.Ticker(ticker)
    info = stock.info

    try:
        # 获取财务数据
        financials = stock.financials
        if financials.empty:
            raise ValueError("No financial data available")

        # 获取最新财务数据的日期
        latest_date = financials.columns[0]
        days_since_update = (datetime.now() - latest_date).days

        # 获取最新的财务数据
        latest_financials = financials.iloc[:, 0]

        # 计算增长率（如果有上一期数据）
        if len(financials.columns) > 1:
            prev_financials = financials.iloc[:, 1]
            revenue_growth = (latest_financials.get("Total Revenue", 0) - prev_financials.get(
                "Total Revenue", 0)) / prev_financials.get("Total Revenue", 1)
            earnings_growth = (latest_financials.get("Net Income", 0) - prev_financials.get(
                "Net Income", 0)) / prev_financials.get("Net Income", 1)
        else:
            revenue_growth = 0
            earnings_growth = 0

        # 构建指标数据
        metrics = {
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("forwardPE", 0),
            "price_to_book": info.get("priceToBook", 0),
            "dividend_yield": info.get("dividendYield", 0),
            "revenue": latest_financials.get("Total Revenue", 0),
            "net_income": latest_financials.get("Net Income", 0),
            "return_on_equity": info.get("returnOnEquity", 0),
            "net_margin": info.get("profitMargins", 0),
            "operating_margin": info.get("operatingMargins", 0),
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "book_value_growth": 0,  # yfinance 不提供这个数据，需要模拟
            "current_ratio": info.get("currentRatio", 0),
            "debt_to_equity": info.get("debtToEquity", 0),
            "free_cash_flow_per_share": info.get("freeCashflow", 0) / info.get("sharesOutstanding", 1) if info.get("sharesOutstanding", 0) > 0 else 0,
            "earnings_per_share": info.get("trailingEps", 0),
            "price_to_earnings_ratio": info.get("forwardPE", 0),
            "price_to_book_ratio": info.get("priceToBook", 0),
            "price_to_sales_ratio": info.get("priceToSalesTrailing12Months", 0),
            # 添加数据时效性信息
            "data_timestamp": latest_date.strftime("%Y-%m-%d"),
            "days_since_update": days_since_update,
            "is_data_recent": days_since_update <= 100  # 是否是最近一个季度的数据
        }

        return [metrics]

    except Exception as e:
        print(f"Error getting financial metrics: {e}")
        return [{
            "market_cap": 0,
            "pe_ratio": 0,
            "price_to_book": 0,
            "dividend_yield": 0,
            "revenue": 0,
            "net_income": 0,
            "return_on_equity": 0,
            "net_margin": 0,
            "operating_margin": 0,
            "revenue_growth": 0,
            "earnings_growth": 0,
            "book_value_growth": 0,
            "current_ratio": 0,
            "debt_to_equity": 0,
            "free_cash_flow_per_share": 0,
            "earnings_per_share": 0,
            "price_to_earnings_ratio": 0,
            "price_to_book_ratio": 0,
            "price_to_sales_ratio": 0,
            "data_timestamp": None,
            "days_since_update": None,
            "is_data_recent": False
        }]


def get_financial_statements(ticker: str) -> Dict[str, Any]:
    """获取财务报表数据"""
    stock = yf.Ticker(ticker)

    try:
        financials = stock.financials  # 获取所有财务数据
        cash_flow = stock.cashflow     # 获取所有现金流数据
        balance = stock.balance_sheet  # 获取所有资产负债表数据

        # 准备最近两个季度的数据
        line_items = []
        for i in range(min(2, len(financials.columns))):
            current_financials = financials.iloc[:, i]
            current_cash_flow = cash_flow.iloc[:, i]
            current_balance = balance.iloc[:, i]

            line_item = {
                "free_cash_flow": current_cash_flow.get("Free Cash Flow", 0),
                "net_income": current_financials.get("Net Income", 0),
                "depreciation_and_amortization": current_cash_flow.get("Depreciation", 0),
                "capital_expenditure": current_cash_flow.get("Capital Expenditure", 0),
                "working_capital": (
                    current_balance.get("Total Current Assets", 0) -
                    current_balance.get("Total Current Liabilities", 0)
                )
            }
            line_items.append(line_item)

        # 如果只有一个季度的数据，复制一份作为前一季度
        if len(line_items) == 1:
            line_items.append(line_items[0])

        return line_items

    except Exception as e:
        print(f"Warning: Error getting financial statements: {e}")
        # 返回两个相同的默认数据
        default_item = {
            "free_cash_flow": 0,
            "net_income": 0,
            "depreciation_and_amortization": 0,
            "capital_expenditure": 0,
            "working_capital": 0
        }
        return [default_item, default_item]


def get_insider_trades(ticker: str) -> List[Dict[str, Any]]:
    """获取内部交易数据"""
    stock = yf.Ticker(ticker)
    try:
        # 获取实际的内部交易数据
        insider_trades = stock.insider_trades
        if insider_trades is None or insider_trades.empty:
            return []

        trades = []
        for _, trade in insider_trades.iterrows():
            trades.append({
                "transaction_shares": int(trade.get("Shares", 0)),
                "transaction_type": "BUY" if trade.get("Shares", 0) > 0 else "SELL",
                "value": float(trade.get("Value", 0)),
                "date": trade.name.strftime("%Y-%m-%d") if hasattr(trade.name, "strftime") else str(trade.name)
            })

        return sorted(trades, key=lambda x: x["date"], reverse=True)
    except Exception as e:
        print(f"Warning: Error getting insider trades: {e}")
        return []


def get_market_data(ticker: str) -> Dict[str, Any]:
    """获取市场数据"""
    stock = yf.Ticker(ticker)
    info = stock.info

    return {
        "market_cap": info.get("marketCap", 0),
        "volume": info.get("volume", 0),
        "average_volume": info.get("averageVolume", 0),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0)
    }


def get_price_history(ticker: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """获取历史价格数据，返回与原项目相同格式的数据"""
    stock = yf.Ticker(ticker)

    # 如果没有提供日期，默认获取过去3个月的数据
    if not end_date:
        end_date = datetime.now()
    else:
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    if not start_date:
        start_date = end_date - timedelta(days=90)
    else:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

        # 获取历史数据
        df = stock.history(start=start_date, end=end_date)

        # 转换为原项目格式的列表
        prices = []
        for date, row in df.iterrows():
            price_dict = {
                "time": date.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"])
            }
            prices.append(price_dict)

        return prices


def prices_to_df(prices: List[Dict[str, Any]]) -> pd.DataFrame:
    """将价格列表转换为 DataFrame，保持与原项目相同的格式"""
    df = pd.DataFrame(prices)
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


def get_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取价格数据并转换为DataFrame格式"""
    try:
        # 将日期字符串转换为datetime对象
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        # 如果是单日查询，扩展结束日期
        if start == end:
            end = start + timedelta(days=1)

        stock = yf.Ticker(ticker)
        df = stock.history(start=start, end=end)

        if df.empty:
            print(
                f"Warning: No price data found for {ticker} between {start_date} and {end_date}")
            # 返回空DataFrame但包含所需的列
            return pd.DataFrame(columns=["Date", "open", "high", "low", "close", "volume"])

        # 重置索引，将日期变为列
        df = df.reset_index()

        # 确保日期列没有时区信息并格式化为字符串
        df["Date"] = df["Date"].dt.tz_localize(None).dt.strftime("%Y-%m-%d")

        # 重命名列以匹配预期格式
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        # 选择需要的列并设置索引
        df = df[["Date", "open", "high", "low", "close", "volume"]]
        df = df.set_index("Date")

        return df

    except Exception as e:
        print(f"Error in get_price_data for {ticker}: {str(e)}")
        # 返回空DataFrame但包含所需的列
        return pd.DataFrame(columns=["Date", "open", "high", "low", "close", "volume"])
