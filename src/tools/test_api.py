import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def test_alpha_vantage_api():
    """测试 Alpha Vantage API 的新闻获取功能"""

    # 获取API密钥
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        print("错误: 未找到 ALPHA_VANTAGE_API_KEY 环境变量")
        return

    # 构建API请求
    symbol = "GOOGL"  # 使用完整的股票代码
    date = datetime.now().strftime("%Y%m%d")
    url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&apikey={api_key}'

    print(f"正在请求 URL: {url}")

    try:
        # 发送请求
        response = requests.get(url)
        data = response.json()

        # 打印完整响应
        print("\nAPI 响应:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # 检查是否有错误信息
        if "Error Message" in data:
            print(f"\n错误: {data['Error Message']}")
        elif "Note" in data:
            print(f"\n提示: {data['Note']}")
        elif "feed" in data:
            print(f"\n成功获取到 {len(data['feed'])} 条新闻")

            # 显示第一条新闻的详细信息
            if data['feed']:
                first_news = data['feed'][0]
                print("\n第一条新闻详情:")
                print(f"标题: {first_news.get('title', '')}")
                print(f"时间: {first_news.get('time_published', '')}")
                print(f"摘要: {first_news.get('summary', '')}")

    except Exception as e:
        print(f"请求出错: {str(e)}")


if __name__ == "__main__":
    test_alpha_vantage_api()
