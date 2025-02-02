import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_yfinance_data(ticker="AAPL", start_date="2023-11-20", end_date="2023-11-25"):
    """测试yfinance返回的数据格式"""
    logger.info(
        f"\nTesting yfinance data for {ticker} from {start_date} to {end_date}")

    # 1. 直接获取历史数据
    stock = yf.Ticker(ticker)
    hist = stock.history(start=start_date, end=end_date)

    logger.info("\n1. Raw history data format:")
    logger.info(f"Type: {type(hist)}")
    logger.info(f"Shape: {hist.shape}")
    logger.info(f"Columns: {hist.columns.tolist()}")
    logger.info("\nFirst few rows:")
    logger.info(hist.head())

    # 2. 测试单日数据
    single_day = start_date
    single_hist = stock.history(start=single_day, end=single_day)

    logger.info(f"\n2. Single day ({single_day}) data:")
    logger.info(f"Empty? {single_hist.empty}")
    if not single_hist.empty:
        logger.info(f"Data:\n{single_hist}")

    # 3. 测试数据转换
    logger.info("\n3. Testing data conversion:")
    try:
        prices = []
        for date, row in hist.iterrows():
            price_dict = {
                "time": date.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"])
            }
            prices.append(price_dict)

        logger.info("Successfully converted data to list of dicts:")
        logger.info(json.dumps(prices[0], indent=2))

        # 转换回DataFrame
        df = pd.DataFrame(prices)
        logger.info("\nConverted back to DataFrame:")
        logger.info(f"Columns: {df.columns.tolist()}")
        logger.info(df.head())

    except Exception as e:
        logger.error(f"Error converting data: {str(e)}")

    # 4. 测试其他可用数据
    logger.info("\n4. Available data attributes:")
    info = stock.info
    logger.info(f"Info keys: {list(info.keys())[:10]}...")  # 只显示前10个键

    return hist


if __name__ == "__main__":
    # 测试过去的数据
    test_yfinance_data("AAPL", "2023-11-20", "2023-11-25")

    # 测试最近的数据
    today = datetime.now()
    five_days_ago = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")
    test_yfinance_data("AAPL", five_days_ago, today_str)
