from datetime import datetime, timedelta
import json
import time
import logging
import matplotlib.pyplot as plt
import pandas as pd
import os
import sys
import matplotlib
import pandas_market_calendars as mcal
import warnings

from main import run_hedge_fund
from tools.api import get_price_data

# Configure Chinese font based on OS
if sys.platform.startswith('win'):
    matplotlib.rc('font', family='Microsoft YaHei')
elif sys.platform.startswith('linux'):
    matplotlib.rc('font', family='WenQuanYi Micro Hei')
else:
    matplotlib.rc('font', family='PingFang SC')

# Enable minus sign display
matplotlib.rcParams['axes.unicode_minus'] = False

# Disable matplotlib warnings
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
warnings.filterwarnings('ignore', category=UserWarning,
                        module='pandas.plotting')
# 禁用所有与plotting相关的警告
logging.getLogger('matplotlib').setLevel(logging.ERROR)
logging.getLogger('PIL').setLevel(logging.ERROR)


class Backtester:
    def __init__(self, agent, ticker, start_date, end_date, initial_capital, num_of_news=5):
        self.agent = agent
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.portfolio = {"cash": initial_capital, "stock": 0}
        self.portfolio_values = []
        self.num_of_news = num_of_news

        # Setup logging
        self.setup_backtest_logging()
        self.logger = self.setup_logging()

        # Initialize API call management
        self._api_call_count = 0
        self._api_window_start = time.time()
        self._last_api_call = 0

        # Initialize market calendar
        self.nyse = mcal.get_calendar('NYSE')

        # Validate inputs
        self.validate_inputs()

    def setup_logging(self):
        """Setup logging system"""
        logger = logging.getLogger('backtester')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def validate_inputs(self):
        """Validate input parameters"""
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")
            if start >= end:
                raise ValueError("Start date must be earlier than end date")
            if self.initial_capital <= 0:
                raise ValueError("Initial capital must be greater than 0")
            if not isinstance(self.ticker, str) or len(self.ticker) == 0:
                raise ValueError("Invalid stock code format")
            # 支持美股代码（如AAPL）和A股代码（如600519）
            if not (self.ticker.isalpha() or (len(self.ticker) == 6 and self.ticker.isdigit())):
                self.backtest_logger.warning(
                    f"Stock code {self.ticker} might be in an unusual format")
            self.backtest_logger.info("Input parameters validated")
        except Exception as e:
            self.backtest_logger.error(
                f"Input parameter validation failed: {str(e)}")
            raise

    def setup_backtest_logging(self):
        """Setup backtest logging"""
        log_dir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)

        self.backtest_logger = logging.getLogger('backtest')
        self.backtest_logger.setLevel(logging.INFO)

        if self.backtest_logger.handlers:
            self.backtest_logger.handlers.clear()

        current_date = datetime.now().strftime('%Y%m%d')
        backtest_period = f"{self.start_date.replace('-', '')}_{self.end_date.replace('-', '')}"
        log_file = os.path.join(
            log_dir, f"backtest_{self.ticker}_{current_date}_{backtest_period}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        self.backtest_logger.addHandler(file_handler)

        self.backtest_logger.info(
            f"Backtest Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.backtest_logger.info(f"Stock Code: {self.ticker}")
        self.backtest_logger.info(
            f"Backtest Period: {self.start_date} to {self.end_date}")
        self.backtest_logger.info(
            f"Initial Capital: {self.initial_capital:,.2f}\n")
        self.backtest_logger.info("-" * 100)

    def is_market_open(self, date_str):
        """Check if the market is open on a given date"""
        schedule = self.nyse.schedule(start_date=date_str, end_date=date_str)
        return not schedule.empty

    def get_previous_trading_day(self, date_str):
        """Get the previous trading day for a given date"""
        date = pd.Timestamp(date_str)
        schedule = self.nyse.schedule(
            start_date=date - pd.Timedelta(days=10),
            end_date=date
        )
        if schedule.empty:
            return None
        return schedule.index[-2].strftime('%Y-%m-%d')

    def get_agent_decision(self, current_date, lookback_start, portfolio, num_of_news):
        """Get agent decision with API rate limiting"""
        max_retries = 3
        current_time = time.time()

        if current_time - self._api_window_start >= 60:
            self._api_call_count = 0
            self._api_window_start = current_time

        if self._api_call_count >= 8:
            wait_time = 60 - (current_time - self._api_window_start)
            if wait_time > 0:
                self.backtest_logger.info(
                    f"API limit reached, waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                self._api_call_count = 0
                self._api_window_start = time.time()

        for attempt in range(max_retries):
            try:
                if self._last_api_call:
                    time_since_last_call = time.time() - self._last_api_call
                    if time_since_last_call < 6:
                        time.sleep(6 - time_since_last_call)

                self._last_api_call = time.time()
                self._api_call_count += 1

                result = self.agent(
                    ticker=self.ticker,
                    start_date=lookback_start,
                    end_date=current_date,
                    portfolio=portfolio,
                    num_of_news=num_of_news
                )

                try:
                    if isinstance(result, str):
                        result = result.replace(
                            '```json\n', '').replace('\n```', '').strip()
                        parsed_result = json.loads(result)

                        formatted_result = {
                            "decision": parsed_result,
                            "analyst_signals": {}
                        }

                        if "agent_signals" in parsed_result:
                            formatted_result["analyst_signals"] = {
                                signal["agent"]: {
                                    "signal": signal.get("signal", "unknown"),
                                    "confidence": signal.get("confidence", 0)
                                }
                                for signal in parsed_result["agent_signals"]
                            }

                        return formatted_result
                    return result
                except json.JSONDecodeError as e:
                    self.backtest_logger.warning(
                        f"JSON parsing error: {str(e)}")
                    self.backtest_logger.warning(f"Raw result: {result}")
                    return {"decision": {"action": "hold", "quantity": 0}, "analyst_signals": {}}

            except Exception as e:
                if "AFC is enabled" in str(e):
                    self.backtest_logger.warning(
                        f"AFC limit triggered, waiting 60 seconds...")
                    time.sleep(60)
                    self._api_call_count = 0
                    self._api_window_start = time.time()
                    continue

                self.backtest_logger.warning(
                    f"Failed to get agent decision (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    return {"decision": {"action": "hold", "quantity": 0}, "analyst_signals": {}}
                time.sleep(2 ** attempt)

    def execute_trade(self, action, quantity, current_price):
        """Execute trade with portfolio constraints"""
        if action == "buy" and quantity > 0:
            cost = quantity * current_price
            if cost <= self.portfolio["cash"]:
                self.portfolio["stock"] += quantity
                self.portfolio["cash"] -= cost
                return quantity
            else:
                max_quantity = int(self.portfolio["cash"] // current_price)
                if max_quantity > 0:
                    self.portfolio["stock"] += max_quantity
                    self.portfolio["cash"] -= max_quantity * current_price
                    return max_quantity
                return 0
        elif action == "sell" and quantity > 0:
            quantity = min(quantity, self.portfolio["stock"])
            if quantity > 0:
                self.portfolio["cash"] += quantity * current_price
                self.portfolio["stock"] -= quantity
                return quantity
            return 0
        return 0

    def run_backtest(self):
        """Run backtest simulation"""
        # Get valid trading days from market calendar
        schedule = self.nyse.schedule(
            start_date=self.start_date, end_date=self.end_date)
        dates = pd.DatetimeIndex([dt.strftime('%Y-%m-%d')
                                 for dt in schedule.index])

        self.backtest_logger.info("\nStarting backtest...")
        print(f"{'Date':<12} {'Code':<6} {'Action':<6} {'Quantity':>8} {'Price':>8} {'Cash':>12} {'Stock':>8} {'Total':>12} {'Bull':>8} {'Bear':>8} {'Neutral':>8}")
        print("-" * 110)

        for current_date in dates:
            current_date_str = current_date.strftime("%Y-%m-%d")

            # Check if market is open
            if not self.is_market_open(current_date_str):
                self.backtest_logger.info(
                    f"Market is closed on {current_date_str} (Holiday), skipping...")
                continue

            # Get previous trading day
            decision_date = self.get_previous_trading_day(current_date_str)
            if decision_date is None:
                self.backtest_logger.warning(
                    f"Could not find previous trading day for {current_date_str}, skipping...")
                continue

            # Use 365-day lookback window
            lookback_start = (pd.Timestamp(current_date_str) -
                              pd.Timedelta(days=365)).strftime("%Y-%m-%d")

            self.backtest_logger.info(
                f"\nProcessing trading day: {current_date_str}")
            self.backtest_logger.info(
                f"Using data up to: {decision_date} (previous trading day)")
            self.backtest_logger.info(
                f"Historical data range: {lookback_start} to {decision_date}")

            # Get current day's price data for trade execution
            try:
                df = get_price_data(
                    self.ticker, current_date_str, current_date_str)
                if df is None or df.empty:
                    self.backtest_logger.warning(
                        f"No price data available for {current_date_str}, skipping...")
                    continue

                # Use opening price for trade execution
                current_price = df.iloc[0]['open']
            except Exception as e:
                self.backtest_logger.error(
                    f"Error getting price data for {current_date_str}: {str(e)}")
                continue

            # Get agent decision based on historical data
            output = self.get_agent_decision(
                decision_date,
                lookback_start,
                self.portfolio,
                self.num_of_news
            )

            self.backtest_logger.info(f"\nTrade Date: {current_date_str}")
            self.backtest_logger.info(
                f"Decision based on data up to: {decision_date}")

            if "analyst_signals" in output:
                self.backtest_logger.info("\nAgent Analysis Results:")
                for agent_name, signal in output["analyst_signals"].items():
                    self.backtest_logger.info(f"\n{agent_name}:")

                    signal_str = f"- Signal: {signal.get('signal', 'unknown')}"
                    if 'confidence' in signal:
                        signal_str += f", Confidence: {signal.get('confidence', 0)*100:.0f}%"
                    self.backtest_logger.info(signal_str)

                    if 'analysis' in signal:
                        self.backtest_logger.info("- Analysis:")
                        analysis = signal['analysis']
                        if isinstance(analysis, dict):
                            for key, value in analysis.items():
                                self.backtest_logger.info(f"  {key}: {value}")
                        elif isinstance(analysis, list):
                            for item in analysis:
                                self.backtest_logger.info(f"  • {item}")
                        else:
                            self.backtest_logger.info(f"  {analysis}")

                    if 'reason' in signal:
                        self.backtest_logger.info("- Decision Rationale:")
                        reason = signal['reason']
                        if isinstance(reason, list):
                            for item in reason:
                                self.backtest_logger.info(f"  • {item}")
                        else:
                            self.backtest_logger.info(f"  • {reason}")

            agent_decision = output.get(
                "decision", {"action": "hold", "quantity": 0})
            action, quantity = agent_decision.get(
                "action", "hold"), agent_decision.get("quantity", 0)

            self.backtest_logger.info("\nFinal Decision:")
            self.backtest_logger.info(f"Action: {action.upper()}")
            self.backtest_logger.info(f"Quantity: {quantity}")
            if "reason" in agent_decision:
                self.backtest_logger.info(
                    f"Reason: {agent_decision['reason']}")

            # Execute trade
            executed_quantity = self.execute_trade(
                action, quantity, current_price)

            # Update portfolio value
            total_value = self.portfolio["cash"] + \
                self.portfolio["stock"] * current_price
            self.portfolio["portfolio_value"] = total_value

            # Record portfolio value
            self.portfolio_values.append({
                "Date": current_date_str,
                "Portfolio Value": total_value,
                "Daily Return": (total_value / self.portfolio_values[-1]["Portfolio Value"] - 1) * 100 if self.portfolio_values else 0
            })

            # Count signals
            bull_count = sum(1 for signal in output.get(
                "analyst_signals", {}).values() if signal.get("signal") == "buy")
            bear_count = sum(1 for signal in output.get(
                "analyst_signals", {}).values() if signal.get("signal") == "sell")
            neutral_count = sum(1 for signal in output.get(
                "analyst_signals", {}).values() if signal.get("signal") == "hold")

            # Print trade record
            print(
                f"{current_date_str:<12} {self.ticker:<6} {action:<6} {executed_quantity:>8} "
                f"{current_price:>8.2f} {self.portfolio['cash']:>12.2f} {self.portfolio['stock']:>8} "
                f"{total_value:>12.2f} {bull_count:>8} {bear_count:>8} {neutral_count:>8}"
            )

        # Analyze backtest results
        self.analyze_performance()

    def analyze_performance(self):
        """Analyze backtest performance"""
        if not self.portfolio_values:
            self.backtest_logger.warning("No portfolio values to analyze")
            return

        try:
            performance_df = pd.DataFrame(self.portfolio_values)
            # 将日期字符串转换为datetime类型
            performance_df['Date'] = pd.to_datetime(performance_df['Date'])
            performance_df = performance_df.set_index('Date')

            # 计算累计收益率
            performance_df["Cumulative Return"] = (
                performance_df["Portfolio Value"] / self.initial_capital - 1) * 100
            performance_df["Portfolio Value (K)"] = performance_df["Portfolio Value"] / 1000

            # 创建子图
            fig, (ax1, ax2) = plt.subplots(
                2, 1, figsize=(12, 10), height_ratios=[1, 1])
            fig.suptitle("Backtest Analysis", fontsize=12)

            # 绘制投资组合价值
            line1 = ax1.plot(performance_df.index, performance_df["Portfolio Value (K)"],
                             label="Portfolio Value", marker='o')
            ax1.set_ylabel("Portfolio Value (K)")
            ax1.set_title("Portfolio Value Change")

            # 添加数据标注
            for x, y in zip(performance_df.index, performance_df["Portfolio Value (K)"]):
                ax1.annotate(f'{y:.1f}K',
                             (x, y),
                             textcoords="offset points",
                             xytext=(0, 10),
                             ha='center')

            # 绘制累计收益率
            line2 = ax2.plot(performance_df.index, performance_df["Cumulative Return"],
                             label="Cumulative Return", color='green', marker='o')
            ax2.set_ylabel("Cumulative Return (%)")
            ax2.set_title("Cumulative Return Change")

            # 添加数据标注
            for x, y in zip(performance_df.index, performance_df["Cumulative Return"]):
                ax2.annotate(f'{y:.1f}%',
                             (x, y),
                             textcoords="offset points",
                             xytext=(0, 10),
                             ha='center')

            plt.xlabel("Date")
            plt.tight_layout()

            # 保存图片
            plt.savefig("backtest_results.png", bbox_inches='tight', dpi=300)
            # 显示图片
            plt.show(block=True)
            # 关闭图形
            plt.close('all')

            # 计算性能指标
            total_return = (
                self.portfolio["portfolio_value"] - self.initial_capital) / self.initial_capital

            # 输出回测总结
            self.backtest_logger.info("\n" + "=" * 50)
            self.backtest_logger.info("Backtest Summary")
            self.backtest_logger.info("=" * 50)
            self.backtest_logger.info(
                f"Initial Capital: {self.initial_capital:,.2f}")
            self.backtest_logger.info(
                f"Final Value: {self.portfolio['portfolio_value']:,.2f}")
            self.backtest_logger.info(
                f"Total Return: {total_return * 100:.2f}%")

            # 计算夏普比率
            daily_returns = performance_df["Daily Return"] / 100
            mean_daily_return = daily_returns.mean()
            std_daily_return = daily_returns.std()
            sharpe_ratio = (mean_daily_return / std_daily_return) * \
                (252 ** 0.5) if std_daily_return != 0 else 0
            self.backtest_logger.info(f"Sharpe Ratio: {sharpe_ratio:.2f}")

            # 计算最大回撤
            rolling_max = performance_df["Portfolio Value"].cummax()
            drawdown = (
                performance_df["Portfolio Value"] / rolling_max - 1) * 100
            max_drawdown = drawdown.min()
            self.backtest_logger.info(f"Maximum Drawdown: {max_drawdown:.2f}%")

            return performance_df
        except Exception as e:
            self.backtest_logger.error(
                f"Error in performance analysis: {str(e)}")
            return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Run backtest simulation')
    parser.add_argument('--ticker', type=str, required=True,
                        help='Stock code (e.g., 600519)')
    parser.add_argument('--end-date', type=str,
                        default=datetime.now().strftime('%Y-%m-%d'),
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str,
                        default=(datetime.now() - timedelta(days=90)
                                 ).strftime('%Y-%m-%d'),
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--initial-capital', type=float,
                        default=100000,
                        help='Initial capital (default: 100000)')
    parser.add_argument('--num-of-news', type=int,
                        default=5,
                        help='Number of news articles to analyze (default: 5)')

    args = parser.parse_args()

    backtester = Backtester(
        agent=run_hedge_fund,
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        num_of_news=args.num_of_news
    )

    backtester.run_backtest()
    
