"""AKShare适配器，用于获取A股数据"""

import logging
import pandas as pd
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import akshare as ak

from src.data.models import Price, FinancialMetrics, CompanyNews, InsiderTrade
from src.utils.ticker_classifier import AssetType


class AKShareAdapter:
    """AKShare数据适配器，专门处理A股数据"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cache = {}  # 简单缓存，后续可以扩展为Redis

    def get_prices(self, ticker: str, start_date: str, end_date: str, **kwargs) -> List[Price]:
        """
        获取A股历史价格数据

        Args:
            ticker: A股ticker (例如: 000001.SZ)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            List[Price]: 价格数据列表
        """
        try:
            # 提取股票代码
            stock_code = self._extract_stock_code(ticker)

            # 使用AKShare获取股票历史数据
            self.logger.info(f"获取A股价格数据: {stock_code} ({start_date} to {end_date})")

            # AKShare获取A股历史数据
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq"  # 前复权
            )

            if df.empty:
                self.logger.warning(f"未获取到数据: {ticker}")
                return []

            # 转换为Price对象
            prices = []
            for _, row in df.iterrows():
                price = Price(
                    time=pd.to_datetime(row['日期']).strftime('%Y-%m-%d'),
                    open=float(row['开盘']),
                    high=float(row['最高']),
                    low=float(row['最低']),
                    close=float(row['收盘']),
                    volume=int(row['成交量']),
                    symbol=ticker
                )
                prices.append(price)

            self.logger.info(f"成功获取 {len(prices)} 条价格数据: {ticker}")
            return sorted(prices, key=lambda x: x.time)

        except Exception as e:
            self.logger.error(f"获取A股价格数据失败 {ticker}: {e}")
            raise

    def get_financial_metrics(self, ticker: str, end_date: str, **kwargs) -> List[FinancialMetrics]:
        """
        获取A股财务指标

        Args:
            ticker: A股ticker
            end_date: 报告期结束日期

        Returns:
            List[FinancialMetrics]: 财务指标列表
        """
        try:
            stock_code = self._extract_stock_code(ticker)
            self.logger.info(f"获取A股财务指标: {stock_code}")

            # AKShare获取财务指标数据
            # 这里使用主要的财务指标接口
            df = ak.stock_financial_analysis_indicator(symbol=stock_code)

            if df.empty:
                self.logger.warning(f"未获取到财务指标数据: {ticker}")
                return []

            # 转换为FinancialMetrics对象
            metrics = []
            for _, row in df.iterrows():
                # 解析报告日期
                report_date = self._parse_report_date(row.get('报告日期', ''))
                if not report_date:
                    continue

                metric = FinancialMetrics(
                    symbol=ticker,
                    date=report_date,
                    period="ttm",  # AKShare通常是年度数据
                    revenue=self._safe_float(row.get('营业收入')),
                    net_income=self._safe_float(row.get('净利润')),
                    gross_margin=self._safe_float(row.get('销售毛利率')),
                    operating_margin=self._safe_float(row.get('营业利润率')),
                    net_margin=self._safe_float(row.get('销售净利率')),
                    roe=self._safe_float(row.get('净资产收益率')),
                    roa=self._safe_float(row.get('总资产报酬率')),
                    debt_to_equity=self._safe_float(row.get('产权比率')),
                    current_ratio=self._safe_float(row.get('流动比率')),
                    quick_ratio=self._safe_float(row.get('速动比率')),
                    pe_ratio=self._safe_float(row.get('市盈率')),
                    pb_ratio=self._safe_float(row.get('市净率')),
                    ps_ratio=self._safe_float(row.get('市销率')),
                    market_cap=self._safe_float(row.get('总市值')),
                    enterprise_value=None  # AKShare可能没有这个数据
                )
                metrics.append(metric)

            self.logger.info(f"成功获取 {len(metrics)} 条财务指标: {ticker}")
            return sorted(metrics, key=lambda x: x.date, reverse=True)

        except Exception as e:
            self.logger.error(f"获取A股财务指标失败 {ticker}: {e}")
            return []

    def get_company_news(self, ticker: str, start_date: str, end_date: str, **kwargs) -> List[CompanyNews]:
        """
        获取A股公司新闻

        Args:
            ticker: A股ticker
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[CompanyNews]: 新闻列表
        """
        try:
            stock_code = self._extract_stock_code(ticker)
            self.logger.info(f"获取A股新闻: {stock_code}")

            # AKShare获取股票新闻
            # 注意：AKShare的新闻接口可能有限制
            df = ak.stock_news_em()

            if df.empty:
                self.logger.warning(f"未获取到新闻数据: {ticker}")
                return []

            # 过滤相关新闻（这里简化处理，实际可能需要更复杂的匹配）
            news_list = []
            for _, row in df.iterrows():
                title = str(row.get('新闻标题', ''))
                content = str(row.get('新闻内容', ''))
                news_date = self._parse_news_date(row.get('发布时间', ''))

                if not news_date or not title:
                    continue

                # 简单的相关性检查（可以改进）
                if stock_code in title or stock_code in content:
                    news = CompanyNews(
                        date=news_date,
                        title=title,
                        source="东方财富",
                        url=row.get('新闻链接', ''),
                        summary=content[:200] if content else "",  # 前200字符作为摘要
                        sentiment="neutral"  # 默认中性，可以后续添加情感分析
                    )
                    news_list.append(news)

            self.logger.info(f"成功获取 {len(news_list)} 条相关新闻: {ticker}")
            return sorted(news_list, key=lambda x: x.date, reverse=True)

        except Exception as e:
            self.logger.error(f"获取A股新闻失败 {ticker}: {e}")
            return []

    def get_insider_trades(self, ticker: str, start_date: str, end_date: str, **kwargs) -> List[InsiderTrade]:
        """
        获取A股内部交易数据

        Args:
            ticker: A股ticker
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            List[InsiderTrade]: 内部交易列表
        """
        try:
            stock_code = self._extract_stock_code(ticker)
            self.logger.info(f"获取A股内部交易: {stock_code}")

            # AKShare获取董监高持股变动
            df = ak.stock_jgdy_em(symbol=stock_code)

            if df.empty:
                self.logger.warning(f"未获取到内部交易数据: {ticker}")
                return []

            trades = []
            for _, row in df.iterrows():
                trade_date = self._parse_trade_date(row.get('变动日期', ''))
                if not trade_date:
                    continue

                trade = InsiderTrade(
                    date=trade_date,
                    insider_name=str(row.get('董监高姓名', '')),
                    insider_title=str(row.get('董监高职务', '')),
                    trade_type=self._classify_trade_type(row.get('变动类型', '')),
                    shares=self._safe_int(row.get('变动数量')),
                    price=self._safe_float(row.get('成交均价')),
                    value=self._safe_float(row.get('变动后持股总数')),
                    symbol=ticker
                )
                trades.append(trade)

            self.logger.info(f"成功获取 {len(trades)} 条内部交易: {ticker}")
            return sorted(trades, key=lambda x: x.date, reverse=True)

        except Exception as e:
            self.logger.error(f"获取A股内部交易失败 {ticker}: {e}")
            return []

    def _extract_stock_code(self, ticker: str) -> str:
        """从ticker中提取股票代码"""
        # 去除交易所后缀
        if '.' in ticker:
            return ticker.split('.')[0]
        return ticker

    def _parse_report_date(self, date_str: str) -> Optional[date]:
        """解析报告日期"""
        try:
            if pd.isna(date_str) or not date_str:
                return None

            # AKShare可能返回不同格式的日期
            if isinstance(date_str, str):
                if '-' in date_str:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    # 可能是YYYYMMDD格式
                    return datetime.strptime(date_str[:8], '%Y%m%d').date()
            return None
        except Exception:
            return None

    def _parse_news_date(self, date_str: str) -> Optional[date]:
        """解析新闻日期"""
        try:
            if pd.isna(date_str) or not date_str:
                return None

            # 新闻日期可能是更复杂的格式
            date_str = str(date_str)

            # 尝试多种日期格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%Y年%m月%d日'
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

            return None
        except Exception:
            return None

    def _parse_trade_date(self, date_str: str) -> Optional[date]:
        """解析交易日期"""
        return self._parse_report_date(date_str)

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if pd.isna(value) or value is None or value == '':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """安全转换为整数"""
        try:
            if pd.isna(value) or value is None or value == '':
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _classify_trade_type(self, trade_type: str) -> str:
        """分类交易类型"""
        trade_type = str(trade_type).lower()

        if '增持' in trade_type or '买入' in trade_type:
            return 'buy'
        elif '减持' in trade_type or '卖出' in trade_type:
            return 'sell'
        else:
            return 'unknown'

    def get_stock_info(self, ticker: str) -> Dict[str, Any]:
        """
        获取A股基本信息

        Args:
            ticker: A股ticker

        Returns:
            Dict: 股票基本信息
        """
        try:
            stock_code = self._extract_stock_code(ticker)

            # 获取股票基本信息
            info = {
                'symbol': ticker,
                'stock_code': stock_code,
                'name': '',
                'industry': '',
                'market': '',
                'listing_date': None
            }

            # 尝试获取股票名称
            try:
                # AKShare获取实时行情数据，包含股票名称
                df = ak.stock_zh_a_spot_em()
                stock_info = df[df['代码'] == stock_code]
                if not stock_info.empty:
                    info['name'] = stock_info.iloc[0].get('名称', '')
                    info['industry'] = stock_info.iloc[0].get('行业', '')
            except Exception as e:
                self.logger.warning(f"获取股票名称失败 {ticker}: {e}")

            return info

        except Exception as e:
            self.logger.error(f"获取A股基本信息失败 {ticker}: {e}")
            return {'symbol': ticker, 'error': str(e)}