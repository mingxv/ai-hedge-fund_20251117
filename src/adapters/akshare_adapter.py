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

            # 尝试多个AKShare财务数据接口
            df = None

            # 方法1: 首先尝试 stock_financial_analysis_indicator
            try:
                df = ak.stock_financial_analysis_indicator(symbol=stock_code)
                if not df.empty:
                    self.logger.info(f"使用 stock_financial_analysis_indicator 获取到数据: {len(df)} 条")
            except Exception as e:
                self.logger.debug(f"stock_financial_analysis_indicator 失败: {e}")

            # 方法2: 如果方法1失败，尝试 stock_financial_abstract
            if df is None or df.empty:
                try:
                    df = ak.stock_financial_abstract(symbol=stock_code)
                    if not df.empty:
                        self.logger.info(f"使用 stock_financial_abstract 获取到数据: {len(df)} 条")
                        df = self._convert_financial_abstract_to_metrics_format(df)
                except Exception as e:
                    self.logger.debug(f"stock_financial_abstract 失败: {e}")

            # 方法3: 如果前两个都失败，尝试基础数据接口
            if df is None or df.empty:
                try:
                    # 获取最基本的财务数据
                    income_df = ak.stock_profit_sheet_by_report_em(symbol=stock_code)
                    balance_df = ak.stock_balance_sheet_by_report_em(symbol=stock_code)

                    if not income_df.empty or not balance_df.empty:
                        self.logger.info(f"使用基础财务报表数据接口获取数据")
                        df = self._combine_financial_statements(income_df, balance_df)
                except Exception as e:
                    self.logger.debug(f"基础财务报表接口失败: {e}")

            if df is None or df.empty:
                self.logger.warning(f"未获取到财务指标数据: {ticker}")
                return []

            # 转换为FinancialMetrics对象
            metrics = []
            for _, row in df.iterrows():
                # 解析报告日期
                report_date = self._parse_report_date(row.get('报告日期', row.get('date', '')))
                if not report_date:
                    continue

                revenue_val = self._safe_float(row.get('营业收入', row.get('revenue', row.get('营业总收入'))))
                net_income_val = self._safe_float(row.get('净利润', row.get('net_income', row.get('归属于母公司所有者的净利润'))))

                metric = FinancialMetrics(
                    ticker=ticker,
                    report_period="quarterly",  # AKShare通常是季度数据
                    period="quarterly",
                    currency="CNY",  # A股使用人民币
                    market_cap=self._safe_float(row.get('总市值', row.get('market_cap'))),
                    enterprise_value=None,  # AKShare可能没有这个数据
                    price_to_earnings_ratio=self._safe_float(row.get('市盈率', row.get('pe_ratio'))),
                    price_to_book_ratio=self._safe_float(row.get('市净率', row.get('pb_ratio'))),
                    price_to_sales_ratio=self._safe_float(row.get('市销率', row.get('ps_ratio'))),
                    enterprise_value_to_ebitda_ratio=None,
                    enterprise_value_to_revenue_ratio=None,
                    free_cash_flow_yield=None,
                    peg_ratio=None,
                    gross_margin=self._safe_float(row.get('销售毛利率', row.get('gross_margin'))),
                    operating_margin=self._safe_float(row.get('营业利润率', row.get('operating_margin'))),
                    net_margin=self._safe_float(row.get('销售净利率', row.get('net_margin'))),
                    return_on_equity=self._safe_float(row.get('净资产收益率', row.get('roe'))),
                    return_on_assets=self._safe_float(row.get('总资产报酬率', row.get('roa', row.get('总资产收益率')))),
                    return_on_invested_capital=None,
                    asset_turnover=None,
                    inventory_turnover=None,
                    receivables_turnover=None,
                    days_sales_outstanding=None,
                    operating_cycle=None,
                    working_capital_turnover=None,
                    current_ratio=self._safe_float(row.get('流动比率', row.get('current_ratio'))),
                    quick_ratio=self._safe_float(row.get('速动比率', row.get('quick_ratio'))),
                    cash_ratio=None,
                    operating_cash_flow_ratio=None,
                    debt_to_equity=self._safe_float(row.get('产权比率', row.get('debt_to_equity', row.get('资产负债率')))),
                    debt_to_assets=None,
                    interest_coverage=None,
                    revenue_growth=None,
                    earnings_growth=None,
                    book_value_growth=None,
                    earnings_per_share_growth=None,
                    free_cash_flow_growth=None,
                    operating_income_growth=None,
                    ebitda_growth=None,
                    payout_ratio=None,
                    earnings_per_share=None,
                    book_value_per_share=None,
                    free_cash_flow_per_share=None
                )
                metrics.append(metric)

            self.logger.info(f"成功获取 {len(metrics)} 条财务指标: {ticker}")
            # FinancialMetrics没有date字段，按report_period排序
            return sorted(metrics, key=lambda x: x.report_period, reverse=True)

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

    def _convert_financial_abstract_to_metrics_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """将stock_financial_abstract的数据转换为标准财务指标格式"""
        try:
            # stock_financial_abstract的格式：选项, 指标, 20250930, 20250630, 20250930...
            # 转换为长格式：报告日期, 指标名称, 值

            # 获取日期列（除了选项和指标列）
            date_columns = [col for col in df.columns if col not in ['选项', '指标'] and col.isdigit()]

            # 创建长格式数据
            rows = []
            for date_col in date_columns[:4]:  # 只取最近4个季度
                # 格式化日期
                formatted_date = f"{date_col[:4]}-{date_col[4:6]}-{date_col[6:8]}"

                # 查找关键指标
                revenue_row = df[df['指标'] == '营业总收入']
                net_income_row = df[df['指标'] == '归母净利润']

                if not revenue_row.empty:
                    revenue_value = revenue_row[date_col].iloc[0]
                else:
                    revenue_value = None

                if not net_income_row.empty:
                    net_income_value = net_income_row[date_col].iloc[0]
                else:
                    net_income_value = None

                # 只添加有数据的行
                if revenue_value is not None or net_income_value is not None:
                    row_data = {
                        '报告日期': formatted_date,
                        '营业收入': revenue_value,
                        '净利润': net_income_value,
                        # 这些指标暂时设为None，后续可以从其他API获取
                        '净资产收益率': None,
                        '市盈率': None,
                        '总市值': None
                    }
                    rows.append(row_data)

            return pd.DataFrame(rows)

        except Exception as e:
            self.logger.error(f"转换财务摘要数据格式失败: {e}")
            return pd.DataFrame()

    def _combine_financial_statements(self, income_df: pd.DataFrame, balance_df: pd.DataFrame) -> pd.DataFrame:
        """合并利润表和资产负债表数据"""
        try:
            # 这是一个简化的实现，实际中需要更复杂的逻辑来合并不同报表的数据
            # 这里优先使用利润表数据
            if not income_df.empty:
                return income_df
            elif not balance_df.empty:
                return balance_df
            else:
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"合并财务报表数据失败: {e}")
            return pd.DataFrame()