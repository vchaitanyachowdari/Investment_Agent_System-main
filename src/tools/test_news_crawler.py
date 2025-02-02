import yfinance as yf
import json
from datetime import datetime
import logging

# 设置日志记录
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('logs/test_news_crawler.log'),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)


def test_news_format(symbol: str = "AAPL"):
    """测试yfinance新闻数据格式"""
    logger.info(f"开始测试 {symbol} 的新闻数据格式...")

    try:
        # 获取股票信息
        stock = yf.Ticker(symbol)

        # 获取新闻数据
        news_data = stock.news
        if not news_data:
            logger.error(f"没有找到 {symbol} 的新闻数据")
            return

            logger.info(f"成功获取到 {len(news_data)} 条新闻")

        # 分析第一条新闻的数据结构
        first_news = news_data[0]
        logger.info("\n完整的第一条新闻数据结构:")
        logger.info(json.dumps(first_news, indent=2, ensure_ascii=False))

        # 分析所有可能的字段
        all_fields = set()
        for news in news_data:
            all_fields.update(news.keys())

        logger.info("\n所有可能的字段:")
        logger.info(json.dumps(list(all_fields), indent=2))

        # 检查每个字段的数据类型和示例值
        field_analysis = {}
        for field in all_fields:
            field_values = []
            field_types = set()
            for news in news_data:
                if field in news:
                    value = news[field]
                    field_values.append(value)
                    field_types.add(type(value).__name__)

            field_analysis[field] = {
                "types": list(field_types),
                "example": field_values[0] if field_values else None,
                "present_in": f"{len(field_values)}/{len(news_data)} news"
            }

        logger.info("\n字段分析:")
        logger.info(json.dumps(field_analysis, indent=2, ensure_ascii=False))

        # 特别检查时间戳字段
        if 'providerPublishTime' in all_fields:
            logger.info("\n时间戳示例:")
        for news in news_data[:3]:  # 只看前3条新闻
            timestamp = news.get('providerPublishTime')
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                logger.info(f"原始时间戳: {timestamp}")
                logger.info(f"转换后时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}", exc_info=True)


if __name__ == "__main__":
    # 测试多个股票的新闻数据
    for symbol in ["AAPL", "MSFT", "GOOGL"]:
        test_news_format(symbol)
        logger.info("\n" + "="*50 + "\n")
