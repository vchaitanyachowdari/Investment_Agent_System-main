import math

from langchain_core.messages import HumanMessage

from agents.state import AgentState, show_agent_reasoning
from tools.api import prices_to_df

import json
import ast

##### Risk Management Agent #####


def risk_management_agent(state: AgentState):
    """Evaluates portfolio risk and sets position limits based on comprehensive risk analysis."""
    show_reasoning = state["metadata"]["show_reasoning"]
    portfolio = state["data"]["portfolio"]
    data = state["data"]

    prices_df = prices_to_df(data["prices"])

    # Fetch messages from other agents
    technical_message = next(
        msg for msg in state["messages"] if msg.name == "technical_analyst_agent")
    fundamentals_message = next(
        msg for msg in state["messages"] if msg.name == "fundamentals_agent")
    sentiment_message = next(
        msg for msg in state["messages"] if msg.name == "sentiment_agent")
    valuation_message = next(
        msg for msg in state["messages"] if msg.name == "valuation_agent")

    try:
        fundamental_signals = json.loads(fundamentals_message.content)
        technical_signals = json.loads(technical_message.content)
        sentiment_signals = json.loads(sentiment_message.content)
        valuation_signals = json.loads(valuation_message.content)
    except Exception as e:
        fundamental_signals = ast.literal_eval(fundamentals_message.content)
        technical_signals = ast.literal_eval(technical_message.content)
        sentiment_signals = ast.literal_eval(sentiment_message.content)
        valuation_signals = ast.literal_eval(valuation_message.content)

    agent_signals = {
        "fundamental": fundamental_signals,
        "technical": technical_signals,
        "sentiment": sentiment_signals,
        "valuation": valuation_signals
    }

    # 1. Calculate Risk Metrics
    returns = prices_df['close'].pct_change().dropna()
    daily_vol = returns.std()
    # Annualized volatility approximation
    volatility = daily_vol * (252 ** 0.5)

    # Calculate volatility distribution
    rolling_std = returns.rolling(window=120).std() * (252 ** 0.5)
    volatility_mean = rolling_std.mean()
    volatility_std = rolling_std.std()
    volatility_percentile = (volatility - volatility_mean) / volatility_std

    # Simple historical VaR at 95% confidence
    var_95 = returns.quantile(0.05)
    # Calculate max drawdown using 60-day window
    max_drawdown = (
        prices_df['close'] / prices_df['close'].rolling(window=60).max() - 1).min()

    # 2. Market Risk Assessment
    market_risk_score = 0

    # Volatility scoring based on percentile
    if volatility_percentile > 1.5:     # Above 1.5 std dev
        market_risk_score += 2
    elif volatility_percentile > 1.0:   # Above 1 std dev
        market_risk_score += 1

    # VaR scoring
    if var_95 < -0.03:
        market_risk_score += 2
    elif var_95 < -0.02:
        market_risk_score += 1

    # Max Drawdown scoring
    if max_drawdown < -0.20:  # Severe drawdown
        market_risk_score += 2
    elif max_drawdown < -0.10:
        market_risk_score += 1

    # 3. Position Size Limits
    current_stock_value = portfolio['stock'] * prices_df['close'].iloc[-1]
    total_portfolio_value = portfolio['cash'] + current_stock_value

    # Start with 25% max position of total portfolio
    base_position_size = total_portfolio_value * 0.25

    if market_risk_score >= 4:
        max_position_size = base_position_size * 0.5  # Reduce for high risk
    elif market_risk_score >= 2:
        max_position_size = base_position_size * \
            0.75  # Slightly reduce for moderate risk
    else:
        max_position_size = base_position_size  # Keep base size for low risk

    # 4. Risk-Adjusted Signals Analysis
    def parse_confidence(conf_str):
        try:
            if isinstance(conf_str, str):
                return float(conf_str.replace('%', '')) / 100.0
            return float(conf_str)
        except:
            return 0.0

    # Check for low confidence signals
    low_confidence = any(parse_confidence(
        signal['confidence']) < 0.30 for signal in agent_signals.values())

    # Check signal divergence
    unique_signals = set(signal['signal'] for signal in agent_signals.values())
    signal_divergence = (2 if len(unique_signals) == 3 else 0)

    # Calculate final risk score
    risk_score = market_risk_score + \
        (2 if low_confidence else 0) + signal_divergence
    risk_score = min(round(risk_score), 10)

    # 5. Determine Trading Action
    # More flexible approach considering technical signals
    technical_confidence = parse_confidence(
        agent_signals['technical']['confidence'])
    fundamental_confidence = parse_confidence(
        agent_signals['fundamental']['confidence'])

    if risk_score >= 9:
        trading_action = "hold"  # Extreme risk, force hold
    elif risk_score >= 7:
        # High risk but consider strong technical signals
        if (technical_signals['signal'] == 'bullish' and technical_confidence > 0.7 and
                fundamental_signals['signal'] == 'bullish'):
            trading_action = "buy"
        else:
            trading_action = "reduce"
    else:
        # Normal risk environment
        if technical_signals['signal'] == 'bullish' and technical_confidence > 0.5:
            trading_action = "buy"
        elif technical_signals['signal'] == 'bearish' and technical_confidence > 0.5:
            trading_action = "sell"
        else:
            trading_action = "hold"

    message_content = {
        "max_position_size": float(max_position_size),
        "risk_score": risk_score,
        "trading_action": trading_action,
        "risk_metrics": {
            "volatility": float(volatility),
            "value_at_risk_95": float(var_95),
            "max_drawdown": float(max_drawdown),
            "market_risk_score": market_risk_score
        },
        "reasoning": f"Risk Score {risk_score}/10: Market Risk={market_risk_score}, "
                     f"Volatility={volatility:.2%}, VaR={var_95:.2%}, "
                     f"Max Drawdown={max_drawdown:.2%}"
    }

    # Create the risk management message
    message = HumanMessage(
        content=json.dumps(message_content),
        name="risk_management_agent",
    )

    if show_reasoning:
        show_agent_reasoning(message_content, "Risk Management Agent")

    return {
        "messages": state["messages"] + [message],
        "data": data,
    }
