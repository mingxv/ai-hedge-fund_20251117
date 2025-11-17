"""yfinance适配器，用于获取加密货币数据"""

import logging
import pandas as pd
import yfinance as yf
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from src.data.models import Price, FinancialMetrics, CompanyNews, InsiderTrade


class YFinanceAdapter:
    """yfinance数据适配器，专门处理加密货币数据"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cache = {}  # 简单缓存

    def get_prices(self, ticker: str, start_date: str, end_date: str, **kwargs) -> List[Price]:
        """
        获取加密货币历史价格数据

        Args:
            ticker: 加密货币symbol (例如: BTC, ETH)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            List[Price]: 价格数据列表
        """
        try:
            # 转换为yfinance格式
            yf_ticker = self._convert_to_yf_format(ticker)

            self.logger.info(f"获取加密货币价格数据: {yf_ticker} ({start_date} to {end_date})")

            # 创建yfinance Ticker对象
            crypto_ticker = yf.Ticker(yf_ticker)

            # 获取历史数据
            hist_data = crypto_ticker.history(
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=True,  # 自动调整股价（拆分等）
                prepost=False
            )

            if hist_data.empty:
                self.logger.warning(f"未获取到价格数据: {ticker}")
                return []

            # 转换为Price对象
            prices = []
            for date, row in hist_data.iterrows():
                price = Price(
                    time=date.strftime('%Y-%m-%d'),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    symbol=f"CRYPTO.{ticker}"
                )
                prices.append(price)

            self.logger.info(f"成功获取 {len(prices)} 条价格数据: {ticker}")
            return prices

        except Exception as e:
            self.logger.error(f"获取加密货币价格数据失败 {ticker}: {e}")
            raise

    def get_financial_metrics(self, ticker: str, end_date: str, **kwargs) -> List[FinancialMetrics]:
        """
        获取加密货币"财务指标"（加密货币没有传统财务指标，返回市场指标）

        Args:
            ticker: 加密货币symbol
            end_date: 报告期结束日期

        Returns:
            List[FinancialMetrics]: 市场指标列表
        """
        try:
            yf_ticker = self._convert_to_yf_format(ticker)
            crypto_ticker = yf.Ticker(yf_ticker)

            self.logger.info(f"获取加密货币市场指标: {ticker}")

            # 获取基本信息
            info = crypto_ticker.info

            # 创建金融指标对象（使用市场相关指标）
            metrics = []

            # 由于加密货币没有传统财务指标，我们使用市场指标
            current_date = datetime.now().date()

            metric = FinancialMetrics(
                symbol=f"CRYPTO.{ticker}",
                date=current_date,
                period="current",
                revenue=None,  # 加密货币没有营业收入
                net_income=None,  # 加密货币没有净利润
                gross_margin=None,
                operating_margin=None,
                net_margin=None,
                roe=None,
                roa=None,
                debt_to_equity=None,
                current_ratio=None,
                quick_ratio=None,
                pe_ratio=self._safe_float(info.get('trailingPE')),
                pb_ratio=self._safe_float(info.get('priceToBook')),
                ps_ratio=None,  # 市销率不太适用于加密货币
                market_cap=self._safe_float(info.get('marketCap')),
                enterprise_value=None
            )
            metrics.append(metric)

            self.logger.info(f"成功获取市场指标: {ticker}")
            return metrics

        except Exception as e:
            self.logger.error(f"获取加密货币市场指标失败 {ticker}: {e}")
            return []

    def get_company_news(self, ticker: str, start_date: str, end_date: str, **kwargs) -> List[CompanyNews]:
        """
        获取加密货币相关新闻

        Args:
            ticker: 加密货币symbol
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[CompanyNews]: 新闻列表
        """
        try:
            yf_ticker = self._convert_to_yf_format(ticker)
            crypto_ticker = yf.Ticker(yf_ticker)

            self.logger.info(f"获取加密货币新闻: {ticker}")

            # 获取新闻数据
            news_data = crypto_ticker.news

            if not news_data:
                self.logger.warning(f"未获取到新闻数据: {ticker}")
                return []

            news_list = []
            for news_item in news_data[:20]:  # 限制数量
                # 解析新闻日期
                publish_date = self._parse_news_date(news_item.get('providerPublishTime'))

                if not publish_date:
                    continue

                news = CompanyNews(
                    date=publish_date,
                    title=news_item.get('title', ''),
                    source=news_item.get('publisher', ''),
                    url=news_item.get('link', ''),
                    summary=news_item.get('summary', ''),
                    sentiment="neutral"  # 默认中性
                )
                news_list.append(news)

            self.logger.info(f"成功获取 {len(news_list)} 条新闻: {ticker}")
            return sorted(news_list, key=lambda x: x.date, reverse=True)

        except Exception as e:
            self.logger.error(f"获取加密货币新闻失败 {ticker}: {e}")
            return []

    def get_insider_trades(self, ticker: str, start_date: str, end_date: str, **kwargs) -> List[InsiderTrade]:
        """
        获取加密货币内部交易（加密货币没有传统内部交易，返回空列表）

        Args:
            ticker: 加密货币symbol
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[InsiderTrade]: 空列表
        """
        self.logger.info(f"加密货币无内部交易数据: {ticker}")
        return []

    def _convert_to_yf_format(self, ticker: str) -> str:
        """
        将ticker转换为yfinance格式

        Args:
            ticker: 原始ticker (例如: BTC, ETH)

        Returns:
            str: yfinance格式ticker (例如: BTC-USD)
        """
        # 常见加密货币映射
        ticker_mapping = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'BNB': 'BNB-USD',
            'XRP': 'XRP-USD',
            'ADA': 'ADA-USD',
            'DOGE': 'DOGE-USD',
            'DOT': 'DOT-USD',
            'MATIC': 'MATIC-USD',
            'LINK': 'LINK-USD',
            'UNI': 'UNI-USD',
            'LTC': 'LTC-USD',
            'BCH': 'BCH-USD',
            'AVAX': 'AVAX-USD',
            'ATOM': 'ATOM-USD',
            'FIL': 'FIL-USD',
            'TRX': 'TRX-USD',
            'ETC': 'ETC-USD',
            'VET': 'VET-USD',
            'THETA': 'THETA-USD',
            'ICP': 'ICP-USD',
            'XLM': 'XLM-USD',
            'NEAR': 'NEAR-USD',
            'ALGO': 'ALGO-USD'
        }

        # 如果有映射，使用映射后的ticker
        yf_ticker = ticker_mapping.get(ticker.upper(), f"{ticker.upper()}-USD")

        self.logger.debug(f"转换ticker: {ticker} -> {yf_ticker}")
        return yf_ticker

    def _parse_news_date(self, timestamp) -> Optional[date]:
        """解析新闻时间戳"""
        try:
            if isinstance(timestamp, (int, float)):
                # yfinance返回的是Unix时间戳
                return datetime.fromtimestamp(timestamp).date()
            elif isinstance(timestamp, str):
                # 尝试解析字符串日期
                try:
                    return datetime.fromisoformat(timestamp.replace('Z', '+00:00')).date()
                except ValueError:
                    # 尝试其他格式
                    return datetime.strptime(timestamp, '%Y-%m-%d').date()
            return None
        except Exception:
            return None

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if value is None or pd.isna(value) or value == '':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_crypto_info(self, ticker: str) -> Dict[str, Any]:
        """
        获取加密货币基本信息

        Args:
            ticker: 加密货币symbol

        Returns:
            Dict: 加密货币基本信息
        """
        try:
            yf_ticker = self._convert_to_yf_format(ticker)
            crypto_ticker = yf.Ticker(yf_ticker)

            info = crypto_ticker.info

            crypto_info = {
                'symbol': f"CRYPTO.{ticker}",
                'yf_symbol': yf_ticker,
                'name': info.get('longName', info.get('shortName', '')),
                'category': 'Cryptocurrency',
                'currency': 'USD',
                'market_cap': self._safe_float(info.get('marketCap')),
                'current_price': self._safe_float(info.get('currentPrice')),
                'day_high': self._safe_float(info.get('dayHigh')),
                'day_low': self._safe_float(info.get('dayLow')),
                'volume': self._safe_int(info.get('volume')),
                '52_week_high': self._safe_float(info.get('fiftyTwoWeekHigh')),
                '52_week_low': self._safe_float(info.get('fiftyTwoWeekLow')),
                'description': info.get('longBusinessSummary', ''),
                'website': info.get('website', ''),
            }

            return crypto_info

        except Exception as e:
            self.logger.error(f"获取加密货币基本信息失败 {ticker}: {e}")
            return {'symbol': f"CRYPTO.{ticker}", 'error': str(e)}

    def _safe_int(self, value) -> Optional[int]:
        """安全转换为整数"""
        try:
            if value is None or pd.isna(value) or value == '':
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def get_supported_cryptos(self) -> List[str]:
        """
        获取支持的加密货币列表

        Returns:
            List[str]: 支持的加密货币符号列表
        """
        return [
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'DOT',
            'MATIC', 'LINK', 'UNI', 'LTC', 'BCH', 'AVAX', 'ATOM',
            'FIL', 'TRX', 'ETC', 'VET', 'THETA', 'ICP', 'XLM',
            'NEAR', 'ALGO'
        ]

    def is_supported(self, ticker: str) -> bool:
        """
        检查是否支持该加密货币

        Args:
            ticker: 加密货币symbol

        Returns:
            bool: 是否支持
        """
        return ticker.upper() in self.get_supported_cryptos()