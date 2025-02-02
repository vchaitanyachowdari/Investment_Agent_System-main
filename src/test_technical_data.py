from datetime import datetime, timedelta
import pandas as pd
import argparse
import os
from tools.api import get_price_data
import json


class TechnicalDataTester:
    def __init__(self, ticker, start_date, end_date):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date

    def calculate_technical_indicators(self, df):
        """Calculate technical indicators for the data"""
        # Moving averages
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA10'] = df['close'].rolling(window=10).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA30'] = df['close'].rolling(window=30).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

        # Bollinger Bands
        df['BB_middle'] = df['close'].rolling(window=20).mean()
        df['BB_upper'] = df['BB_middle'] + 2 * \
            df['close'].rolling(window=20).std()
        df['BB_lower'] = df['BB_middle'] - 2 * \
            df['close'].rolling(window=20).std()

        # Volume indicators
        df['Volume_MA5'] = df['volume'].rolling(window=5).mean()
        df['Volume_MA20'] = df['volume'].rolling(window=20).mean()

        return df

    def run_test(self):
        """Run the technical analysis test"""
        print(f"\nStarting technical analysis test for {self.ticker}")
        print(f"Period: {self.start_date} to {self.end_date}")
        print("-" * 100)

        # Get all trading days in the period
        dates = pd.date_range(self.start_date, self.end_date, freq="B")

        for current_date in dates:
            current_date_str = current_date.strftime("%Y-%m-%d")
            decision_date = (current_date - timedelta(days=1)
                             ).strftime("%Y-%m-%d")
            lookback_start = (
                current_date - timedelta(days=365)).strftime("%Y-%m-%d")

            print(f"\nAnalyzing trading day: {current_date_str}")
            print(f"Using data up to: {decision_date} (previous trading day)")
            print("Historical data range:", lookback_start, "to", decision_date)

            # Get historical data up to previous day
            df = get_price_data(self.ticker, lookback_start, decision_date)
            if df is None or df.empty:
                print(f"No data available for decision date {decision_date}")
                continue

            # Calculate technical indicators
            df = self.calculate_technical_indicators(df)

            # Get the last day's indicators (which is the decision date)
            decision_data = df.iloc[-1]

            # Get current day's opening price (this would be the execution price)
            current_day_data = get_price_data(
                self.ticker, current_date_str, current_date_str)
            if current_day_data is not None and not current_day_data.empty:
                execution_price = current_day_data.iloc[0]['open']
            else:
                print(
                    f"Warning: Could not get opening price for {current_date_str}")
                continue

            # Create technical analysis summary
            technical_data = {
                "decision_date": decision_date,
                "trading_date": current_date_str,
                "execution_price": round(execution_price, 2),
                "previous_close": round(decision_data['close'], 2),
                "moving_averages": {
                    "MA5": round(decision_data['MA5'], 2),
                    "MA10": round(decision_data['MA10'], 2),
                    "MA20": round(decision_data['MA20'], 2),
                    "MA30": round(decision_data['MA30'], 2)
                },
                "momentum": {
                    "RSI": round(decision_data['RSI'], 2),
                    "MACD": round(decision_data['MACD'], 4),
                    "MACD_Signal": round(decision_data['Signal_Line'], 4)
                },
                "volatility": {
                    "Bollinger_Upper": round(decision_data['BB_upper'], 2),
                    "Bollinger_Middle": round(decision_data['BB_middle'], 2),
                    "Bollinger_Lower": round(decision_data['BB_lower'], 2)
                },
                "volume": {
                    "previous_volume": int(decision_data['volume']),
                    "Volume_MA5": int(decision_data['Volume_MA5']),
                    "Volume_MA20": int(decision_data['Volume_MA20'])
                }
            }

            # Print technical analysis data
            print("\nTechnical Analysis Data:")
            print(json.dumps(technical_data, indent=2))

            # Print key signals
            print("\nKey Signals:")
            print(
                f"Price vs MA20: {'Above' if decision_data['close'] > decision_data['MA20'] else 'Below'} MA20")
            print(
                f"RSI Status: {'Overbought' if decision_data['RSI'] > 70 else 'Oversold' if decision_data['RSI'] < 30 else 'Neutral'}")
            print(
                f"MACD Signal: {'Bullish' if decision_data['MACD'] > decision_data['Signal_Line'] else 'Bearish'}")
            print(
                f"Volume vs Average: {'Above' if decision_data['volume'] > decision_data['Volume_MA20'] else 'Below'} 20-day average")
            print("-" * 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Test technical indicators calculation')
    parser.add_argument('--ticker', type=str, required=True,
                        help='Stock ticker symbol')
    parser.add_argument('--start-date', type=str, required=True,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True,
                        help='End date (YYYY-MM-DD)')

    args = parser.parse_args()

    tester = TechnicalDataTester(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date
    )

    tester.run_test()
