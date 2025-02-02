from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from tools.openrouter_config import get_chat_completion

from agents.state import AgentState, show_agent_reasoning


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading decisions and generates orders"""
    show_reasoning = state["metadata"]["show_reasoning"]
    portfolio = state["data"]["portfolio"]

    # Get the technical analyst, fundamentals agent, and risk management agent messages
    technical_message = next(
        msg for msg in state["messages"] if msg.name == "technical_analyst_agent")
    fundamentals_message = next(
        msg for msg in state["messages"] if msg.name == "fundamentals_agent")
    sentiment_message = next(
        msg for msg in state["messages"] if msg.name == "sentiment_agent")
    valuation_message = next(
        msg for msg in state["messages"] if msg.name == "valuation_agent")
    risk_message = next(
        msg for msg in state["messages"] if msg.name == "risk_management_agent")

    # Create the system message
    system_message = {
        "role": "system",
        "content": """You are a portfolio manager making final trading decisions.
            Your job is to make a trading decision based on the team's analysis while considering
            risk management guidelines.

            RISK MANAGEMENT GUIDELINES:
            - Try to stay within max_position_size from risk management when possible
            - Consider risk management's trading_action as a strong recommendation
            - Risk signals should be weighed against potential opportunities

            When weighing the different signals for direction and timing:
            1. Technical Analysis (35% weight)
               - Primary driver for short-term trading decisions
               - Key for entry/exit timing
               - Higher weight for more active trading
            
            2. Fundamental Analysis (30% weight)
               - Business quality and growth assessment
               - Determines conviction in position
            
            3. Valuation Analysis (25% weight)
               - Long-term value assessment
               - Secondary confirmation of entry/exit points
            
            4. Sentiment Analysis (10% weight)
               - Final consideration
               - Can influence sizing and timing
            
            The decision process should be:
            1. Evaluate technical signals for timing
            2. Check fundamental support
            3. Confirm with valuation
            4. Consider sentiment
            5. Apply risk management as guidelines
            
            Provide the following in your output:
            - "action": "buy" | "sell" | "hold",
            - "quantity": <positive integer>
            - "confidence": <float between 0 and 1>
            - "agent_signals": <list of agent signals including agent name, signal (bullish | bearish | neutral), and their confidence>
            - "reasoning": <concise explanation of the decision including how you weighted the signals>

            Trading Rules:
            - Try to stay within risk management position limits when possible
            - Only buy if you have available cash
            - Only sell if you have shares to sell
            - Quantity must be ≤ current position for sells
            - Consider max_position_size from risk management as a guideline"""
    }

    # Create the user message
    user_message = {
        "role": "user",
        "content": f"""Based on the team's analysis below, make your trading decision.

            Technical Analysis Trading Signal: {technical_message.content}
            Fundamental Analysis Trading Signal: {fundamentals_message.content}
            Sentiment Analysis Trading Signal: {sentiment_message.content}
            Valuation Analysis Trading Signal: {valuation_message.content}
            Risk Management Trading Signal: {risk_message.content}

            Here is the current portfolio:
            Portfolio:
            Cash: {portfolio['cash']:.2f}
            Current Position: {portfolio['stock']} shares

            Only include the action, quantity, reasoning, confidence, and agent_signals in your output as JSON.  Do not include any JSON markdown.

            Remember, the action must be either buy, sell, or hold.
            You can only buy if you have available cash.
            You can only sell if you have shares in the portfolio to sell."""
    }

    # Get the completion from OpenRouter
    result = get_chat_completion([system_message, user_message])

    # 如果 API 调用失败,返回默认的 hold 决策
    if result is None:
        result = '''
        {
            "action": "hold",
            "quantity": 0,
            "confidence": 0.5,
            "agent_signals": [
                {"name": "technical_analyst", "signal": "neutral", "confidence": 0.5},
                {"name": "fundamentals", "signal": "neutral", "confidence": 0.5},
                {"name": "sentiment", "signal": "neutral", "confidence": 0.5},
                {"name": "valuation", "signal": "neutral", "confidence": 0.5},
                {"name": "risk_management", "signal": "hold", "confidence": 1.0}
            ],
            "reasoning": "API call failed, defaulting to hold position for safety"
        }
        '''

    # Create the portfolio management message
    message = HumanMessage(
        content=result,
        name="portfolio_management",
    )

    # Print the decision if the flag is set
    if show_reasoning:
        show_agent_reasoning(message.content, "Portfolio Management Agent")

    return {"messages": state["messages"] + [message]}
