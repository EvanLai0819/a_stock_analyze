---
name: "stock-analysis"
description: "Analyzes A-share stocks with multi-dimensional scoring and generates decision dashboards. Invoke when user requests stock analysis, asks for buy/sell recommendations, or wants to view stock reports."
---

# Stock Analysis Skill

This skill provides comprehensive stock analysis capabilities for the daily_stock_analysis project, an AI-powered A-share stock intelligent analysis system.

## Core Capabilities

### 1. Multi-Dimensional Analysis
- **Technical Analysis**: MA5/MA10/MA20 trend analysis, bias rate calculation, support/resistance levels
- **Chip Distribution**: Profit ratio, average cost, concentration analysis
- **Capital Flow**: Main force net inflow, individual stock capital flow, industry capital flow
- **News Intelligence**: Latest news, institutional analysis, risk alerts, performance expectations
- **Real-time Quotes**: Current price, volume ratio, turnover rate, amplitude

### 2. AI Decision Dashboard
- One-sentence core conclusion
- Precise buy/sell points with exact prices
- Position management recommendations
- Operation checklist with clear status indicators (✅/⚠️/❌)

### 3. Market Review
- Daily market overview
- Sector performance ranking
- Northbound capital flow tracking
- Industry capital flow analysis

### 4. Backtest Validation
- Historical analysis accuracy verification
- Direction win rate calculation
- Stop-profit/stop-loss hit rate

## Usage Examples

### Analyze Specific Stocks

```bash
# Analyze single stock
python main.py --stocks 600276 --single-notify

# Analyze multiple stocks
python main.py --stocks 600519,000001,300750

# Dry-run mode (data collection only, no AI analysis)
python main.py --dry-run
```

### Market Review Only

```bash
# Run market review without individual stock analysis
python main.py --market-review
```

### Configuration

Before running, ensure proper configuration in `.env` file:

**Required Configuration:**
- `STOCK_LIST`: Stock codes to analyze (e.g., `600519,hk00700,AAPL`)
- AI Model API Key: Either `GEMINI_API_KEY` or `OPENAI_API_KEY`

**Recommended Configuration:**
- `TAVILY_API_KEYS`: For news search
- `TUSHARE_TOKEN`: For enhanced data access
- Notification channels: `WECHAT_WEBHOOK_URL`, `FEISHU_WEBHOOK_URL`, `EMAIL_SENDER`, etc.

## Analysis Workflow

1. **Data Collection**: Fetch real-time quotes, historical data, capital flow, chip distribution
2. **News Intelligence**: Search for latest news, institutional analysis, risk alerts
3. **Industry Analysis**: Get industry classification and industry capital flow data
4. **AI Analysis**: Generate comprehensive analysis with decision recommendations
5. **Report Generation**: Create detailed markdown report with decision dashboard
6. **Notification**: Push report to configured channels (WeChat, Feishu, Email, etc.)

## Report Structure

Generated reports include:

### 📰 Important Information
- Industry capital flow (net inflow/outflow, ranking)
- News sentiment analysis
- Performance expectations
- Risk alerts
- Positive catalysts

### 📌 Core Conclusion
- Decision type: Buy/Hold/Sell
- Trend prediction
- One-sentence decision rationale
- Urgency level

### 📈 Market Data
- Current price and changes
- Volume ratio and turnover rate
- MA system status
- Chip distribution metrics

### 🎯 Trading Strategy
- Ideal buy point
- Secondary buy point
- Stop-loss level
- Target price
- Position recommendation
- Operation checklist

## Integration Points

### Data Sources (Priority Order)
1. Tushare Pro (requires token, highest priority)
2. Efinance (East Money data)
3. Akshare (free, comprehensive)
4. Pytdx (通达信)
5. Baostock
6. YFinance (for HK/US stocks)

### AI Models Supported
- Gemini (free, recommended)
- OpenAI compatible APIs (DeepSeek, Qwen, Claude)
- Ollama (local deployment)

### Notification Channels
- Enterprise WeChat
- Feishu (Lark)
- Telegram
- DingTalk
- Email
- Pushover
- Custom Webhook

## Key Features

### Trading Discipline Built-in
- **No chasing highs**: Bias rate > 5% triggers risk alert
- **Trend trading**: Only trade when MA5 > MA10 > MA20 (bullish alignment)
- **Precise points**: Exact buy/sell/stop-loss/target prices
- **Checklist verification**: Each condition marked as ✅/⚠️/❌

### Fallback Mechanisms
- Multi-source data fetching with automatic fallback
- Industry capital flow fallback: uses individual stock capital flow as proxy when industry data unavailable
- API rate limit handling with retry logic

### Analysis Dimensions
- **Technical Score**: MA trend, bias rate, volume ratio
- **Capital Score**: Main force flow, industry flow, northbound capital
- **Fundamental Score**: Financial metrics, institutional holdings
- **News Score**: Sentiment analysis, risk level, catalyst strength
- **Market Environment**: Sector performance, overall market trend

## Common Use Cases

1. **Daily Analysis**: Run automated analysis for watchlist stocks
2. **Quick Check**: Analyze specific stock before trading decision
3. **Market Overview**: Get daily market review without individual analysis
4. **Backtest Validation**: Verify historical analysis accuracy
5. **Report Review**: View generated analysis reports in `reports/` directory

## File Locations

- **Reports**: `reports/report_YYYYMMDD.md`
- **Logs**: `logs/stock_analysis_YYYYMMDD.log`
- **Database**: `data/stock_analysis.db`
- **Configuration**: `.env` (copy from `.env.example`)

## Notes

- Analysis typically takes 2-5 minutes per stock
- Tushare API has rate limits (some interfaces require 6000+ points)
- Industry capital flow may use fallback mechanism when API fails
- Reports are generated in Markdown format with rich formatting
- All analysis results are stored in SQLite database for historical tracking

## Related Documentation

- Full Guide: `docs/full-guide.md`
- FAQ: `docs/FAQ.md`
- Deployment: `docs/DEPLOY.md`
- Bot Commands: `docs/bot-command.md`