import datetime
import os
import pandas as pd
import requests
import time

from src.data.cache import get_cache
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

# 多API支持
from src.utils.ticker_classifier import TickerClassifier, AssetType
from src.utils.api_router import api_router
from src.adapters.akshare_adapter import AKShareAdapter
from src.adapters.yfinance_adapter import YFinanceAdapter

# Global cache instance
_cache = get_cache()


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and moderate backoff.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
    
    Returns:
        requests.Response: The response object
    
    Raises:
        Exception: If the request fails with a non-429 error
    """
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 429 and attempt < max_retries:
            # Linear backoff: 60s, 90s, 120s, 150s...
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue
        
        # Return the response (whether success, other errors, or final 429)
        return response


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """
    智能获取价格数据，支持多种资产类型

    Args:
        ticker: 资产ticker（支持美股、A股、加密货币）
        start_date: 开始日期
        end_date: 结束日期
        api_key: API密钥（用于FinancialDatasets）

    Returns:
        list[Price]: 价格数据列表
    """
    # 创建包含所有参数的缓存键
    cache_key = f"{ticker}_{start_date}_{end_date}"

    # 检查缓存
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # 识别资产类型
    asset_type, normalized_ticker = TickerClassifier.classify(ticker)

    try:
        # 使用智能路由获取数据
        prices = api_router.route_request(
            function_name="get_prices",
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key
        )

        if not prices:
            return []

        # 缓存结果
        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
        return prices

    except Exception as e:
        # 对于美股类型，如果智能路由失败，尝试使用原有逻辑
        if asset_type == AssetType.US_STOCK:
            print(f"智能路由失败，尝试使用原有API获取 {ticker}: {e}")
            return get_prices_original(ticker, start_date, end_date, api_key)

        # 对于其他类型，记录错误并重新抛出
        print(f"获取价格数据失败 {ticker} (类型: {asset_type.value}): {e}")
        raise


def get_prices_original(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """
    原有的价格获取函数，作为降级方案

    Args:
        ticker: 资产ticker（仅支持FinancialDatasets覆盖的资产）
        start_date: 开始日期
        end_date: 结束日期
        api_key: API密钥

    Returns:
        list[Price]: 价格数据列表
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}_original"

    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

    # Parse response with Pydantic model
    price_response = PriceResponse(**response.json())
    prices = price_response.prices

    if not prices:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """
    智能获取财务指标数据，支持多种资产类型

    Args:
        ticker: 资产ticker（支持美股、A股、加密货币）
        end_date: 结束日期
        period: 报告期
        limit: 返回数量限制
        api_key: API密钥

    Returns:
        list[FinancialMetrics]: 财务指标数据列表
    """
    # 创建缓存键
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"

    # 检查缓存
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # 识别资产类型
    asset_type, normalized_ticker = TickerClassifier.classify(ticker)

    try:
        # 使用智能路由获取数据
        metrics = api_router.route_request(
            function_name="get_financial_metrics",
            ticker=ticker,
            end_date=end_date,
            period=period,
            limit=limit,
            api_key=api_key
        )

        if not metrics:
            return []

        # 缓存结果
        _cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])
        return metrics

    except Exception as e:
        # 对于美股类型，如果智能路由失败，尝试使用原有逻辑
        if asset_type == AssetType.US_STOCK:
            print(f"智能路由失败，尝试使用原有API获取财务指标 {ticker}: {e}")
            return get_financial_metrics_original(ticker, end_date, period, limit, api_key)

        # 对于其他类型，记录错误并重新抛出
        print(f"获取财务指标失败 {ticker} (类型: {asset_type.value}): {e}")
        raise


def get_financial_metrics_original(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """
    原有的财务指标获取函数，作为降级方案
    """
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}_original"

    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

    # Parse response with Pydantic model
    metrics_response = FinancialMetricsResponse(**response.json())
    financial_metrics = metrics_response.financial_metrics

    if not financial_metrics:
        return []

    # Cache the results as dicts using the comprehensive cache key
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch line items from API with multi-API routing support."""

    # 首先识别资产类型
    asset_type, normalized_ticker = TickerClassifier.classify(ticker)

    # 美股使用 Financial Datasets API 获取传统财务指标数据
    if asset_type == AssetType.US_STOCK:
        return _search_us_stock_line_items(normalized_ticker, line_items, end_date, period, limit, api_key)

    # A股使用 AKShare 获取财务指标数据
    elif asset_type == AssetType.A_STOCK:
        return _search_a_stock_line_items(normalized_ticker, line_items, end_date, limit)

    # 加密货币没有传统财务指标数据，返回空列表并给出明确说明
    elif asset_type == AssetType.CRYPTO:
        print(f"注意: {ticker} 是加密货币，没有传统财务指标数据（如收入、利润等）")
        return []

    # 其他资产类型暂不支持财务指标数据
    else:
        print(f"注意: {ticker} ({asset_type.value}) 暂不支持财务指标数据查询")
        return []


def _search_us_stock_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """获取美股的传统财务指标数据"""
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    response = _make_api_request(url, headers, method="POST", json_data=body)
    if response.status_code != 200:
        raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")
    data = response.json()
    response_model = LineItemResponse(**data)
    search_results = response_model.search_results
    if not search_results:
        return []

    # Cache the results
    return search_results[:limit]


def _search_a_stock_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    limit: int = 10
) -> list[LineItem]:
    """获取A股的财务指标数据，转换为LineItem格式"""
    try:
        import akshare as ak

        # 移除A股后缀，获取纯代码
        a_stock_code = ticker
        for suffix in ['.SZ', '.SS', '.SH', '.BJ']:
            if ticker.endswith(suffix):
                a_stock_code = ticker[:-3]
                break

        # 使用已验证可用的 stock_financial_abstract 接口
        df = ak.stock_financial_abstract(symbol=a_stock_code)

        if df.empty:
            print(f"注意: {ticker} 暂无财务指标数据")
            return []

        # 将常见的A股财务指标映射到标准化的line items
        line_item_mapping = {
            'revenue': ['营业总收入'],
            'net_income': ['归母净利润'],
            'total_assets': ['资产总计'],
            'total_liabilities': ['负债合计'],
            'current_assets': ['流动资产合计'],
            'current_liabilities': ['流动负债合计'],
            'book_value': ['股东权益合计', '归属于母公司所有者权益合计'],
            'book_value_per_share': ['每股净资产'],
            'operating_income': ['营业利润'],
            'eps': ['基本每股收益'],
            'earnings_per_share': ['基本每股收益'],  # 添加eps别名，兼容代理代码
            'roe': ['净资产收益率'],
            'roa': ['总资产收益率'],
            'gross_profit': ['营业毛利'],
            'operating_cash_flow': ['经营活动产生的现金流量净额'],
            'free_cash_flow': ['自由现金流量'],
            'dividends_and_other_cash_distributions': ['分红派息'],
            'outstanding_shares': ['总股本']
        }

        result = []
        for requested_item in line_items:
            # 查找对应的A股财务指标
            if requested_item in line_item_mapping:
                chinese_names = line_item_mapping[requested_item]
                value = None

                for chinese_name in chinese_names:
                    # 在数据中查找对应的指标行
                    matching_row = df[df['指标'] == chinese_name]
                    if not matching_row.empty:
                        # 获取最新一期的数据（第3列是最新数据）
                        value = matching_row.iloc[0, 2]  # 第3列（索引2）是最新数据
                        break

                if value is not None and pd.notna(value) and value != 0:
                    # 创建LineItem对象
                    line_item = LineItem(
                        ticker=ticker,
                        report_period="quarterly",  # AKShare通常是季度数据
                        period="quarterly",
                        currency="CNY",
                        name=requested_item,
                        value=float(value)
                    )
                    result.append(line_item)

        if result:
            print(f"✅ 成功获取 {ticker} 的 {len(result)} 项财务指标数据")
        else:
            print(f"⚠️ {ticker} 暂无匹配的财务指标数据")

        return result[:limit]

    except Exception as e:
        print(f"⚠️ 获取A股 {ticker} 财务指标数据失败: {e}")
        return []


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = InsiderTradeResponse(**data)
        insider_trades = response_model.insider_trades

        if not insider_trades:
            break

        all_trades.extend(insider_trades)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(insider_trades) < limit:
            break

        # Update end_date to the oldest filing date from current batch for next iteration
        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_trades:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from cache or API."""
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {ticker} - {response.status_code} - {response.text}")

        data = response.json()
        response_model = CompanyNewsResponse(**data)
        company_news = response_model.news

        if not company_news:
            break

        all_news.extend(company_news)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(company_news) < limit:
            break

        # Update end_date to the oldest date from current batch for next iteration
        current_end_date = min(news.date for news in company_news).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_news:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from the API with multi-API routing support."""

    # 首先识别资产类型
    asset_type, normalized_ticker = TickerClassifier.classify(ticker)

    # 对于非美股资产，使用路由系统获取财务指标
    if asset_type != AssetType.US_STOCK:
        try:
            # 使用路由系统获取财务指标
            financial_metrics = api_router.route_request('get_financial_metrics', normalized_ticker, end_date=end_date)
            if financial_metrics:
                return financial_metrics[0].market_cap
            else:
                print(f"注意: {ticker} ({asset_type.value}) 无法获取市值数据")
                return None
        except Exception as e:
            print(f"注意: {ticker} ({asset_type.value}) 获取市值数据失败: {e}")
            return None

    # 只有美股才使用 Financial Datasets API
    # Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/company/facts/?ticker={normalized_ticker}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None

        data = response.json()
        response_model = CompanyFactsResponse(**data)
        return response_model.company_facts.market_cap

    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
