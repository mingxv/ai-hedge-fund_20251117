"""多API路由系统，根据资产类型智能路由到对应的数据源"""

import logging
import time
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, date
from enum import Enum

from src.utils.ticker_classifier import AssetType, TickerClassifier
from src.data.models import Price, FinancialMetrics, CompanyNews, InsiderTrade

# 延迟导入以避免循环依赖
def _get_financial_datasets_prices(*args, **kwargs):
    from src.tools.api import get_prices_original
    return get_prices_original(*args, **kwargs)

def _get_financial_datasets_metrics(*args, **kwargs):
    from src.tools.api import get_financial_metrics_original
    return get_financial_metrics_original(*args, **kwargs)

# 导入适配器
from src.adapters.akshare_adapter import AKShareAdapter
from src.adapters.yfinance_adapter import YFinanceAdapter


class APIProvider(Enum):
    """API提供商枚举"""
    FINANCIAL_DATASETS = "financialdatasets"
    AKSHARE = "akshare"
    YFINANCE = "yfinance"
    UNKNOWN = "unknown"


class APIRouter:
    """多API路由器，根据资产类型选择合适的数据源"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # 初始化适配器
        self.akshare_adapter = AKShareAdapter()
        self.yfinance_adapter = YFinanceAdapter()

        self.api_endpoints = {
            AssetType.US_STOCK: self._route_us_stock,
            AssetType.A_STOCK: self._route_a_stock,
            AssetType.HK_STOCK: self._route_hk_stock,
            AssetType.CRYPTO: self._route_crypto,
            AssetType.UNKNOWN: self._route_unknown
        }

        # API调用统计
        self.api_call_stats = {
            APIProvider.FINANCIAL_DATASETS: {"calls": 0, "errors": 0},
            APIProvider.AKSHARE: {"calls": 0, "errors": 0},
            APIProvider.YFINANCE: {"calls": 0, "errors": 0},
        }

    def route_request(self, function_name: str, ticker: str, **kwargs) -> Any:
        """
        根据资产类型路由API请求到对应的数据源

        Args:
            function_name: API函数名称 ('get_prices', 'get_financial_metrics', etc.)
            ticker: 资产ticker
            **kwargs: 其他API参数

        Returns:
            API响应数据
        """
        # 识别资产类型
        asset_type, normalized_ticker = TickerClassifier.classify(ticker)

        # 路由到对应的处理函数
        start_time = time.time()
        try:
            result = self.api_endpoints[asset_type](
                function_name,
                normalized_ticker,
                **kwargs
            )

            # 记录成功调用
            response_time = time.time() - start_time
            self._log_api_call(asset_type, ticker, function_name, True, response_time)

            return result

        except Exception as e:
            # 记录失败调用
            response_time = time.time() - start_time
            self._log_api_call(asset_type, ticker, function_name, False, response_time, str(e))

            # 对于美股类型，尝试降级到FinancialDatasets
            if asset_type == AssetType.US_STOCK:
                return self._try_fallback_financial_datasets(function_name, ticker, **kwargs)

            raise

    def _route_us_stock(self, function_name: str, ticker: str, **kwargs) -> Any:
        """美股数据路由"""
        return self._call_financial_datasets_api(function_name, ticker, **kwargs)

    def _route_hk_stock(self, function_name: str, ticker: str, **kwargs) -> Any:
        """港股数据路由（使用FinancialDatasets）"""
        return self._call_financial_datasets_api(function_name, ticker, **kwargs)

    def _route_a_stock(self, function_name: str, ticker: str, **kwargs) -> Any:
        """A股数据路由（使用AKShare）"""
        # 暂时返回空列表，后续实现AKShare集成
        self.logger.info(f"A股数据请求 {ticker} - 函数: {function_name}")

        if function_name == "get_prices":
            return self._get_a_stock_prices(ticker, **kwargs)
        elif function_name == "get_financial_metrics":
            return self._get_a_stock_metrics(ticker, **kwargs)
        elif function_name == "get_company_news":
            return self._get_a_stock_news(ticker, **kwargs)
        elif function_name == "get_insider_trades":
            return self._get_a_stock_insider_trades(ticker, **kwargs)
        else:
            raise ValueError(f"不支持的功能: {function_name}")

    def _route_crypto(self, function_name: str, ticker: str, **kwargs) -> Any:
        """加密货币数据路由（使用yfinance）"""
        self.logger.info(f"加密货币数据请求 {ticker} - 函数: {function_name}")

        if function_name == "get_prices":
            return self._get_crypto_prices(ticker, **kwargs)
        elif function_name == "get_financial_metrics":
            # 加密货币没有传统财务指标，返回空列表
            return []
        elif function_name == "get_company_news":
            return self._get_crypto_news(ticker, **kwargs)
        elif function_name == "get_insider_trades":
            # 加密货币没有内部交易，返回空列表
            return []
        else:
            raise ValueError(f"不支持的功能: {function_name}")

    def _route_unknown(self, function_name: str, ticker: str, **kwargs) -> Any:
        """未知类型处理"""
        self.logger.warning(f"未知资产类型: {ticker}，尝试使用FinancialDatasets")
        return self._call_financial_datasets_api(function_name, ticker, **kwargs)

    def _call_financial_datasets_api(self, function_name: str, ticker: str, **kwargs) -> Any:
        """调用FinancialDatasets API"""
        try:
            if function_name == "get_prices":
                result = _get_financial_datasets_prices(ticker, **kwargs)
                self.api_call_stats[APIProvider.FINANCIAL_DATASETS]["calls"] += 1
                return result
            elif function_name == "get_financial_metrics":
                result = _get_financial_datasets_metrics(ticker, **kwargs)
                self.api_call_stats[APIProvider.FINANCIAL_DATASETS]["calls"] += 1
                return result
            # 暂时注释新闻和内部交易，后续实现
            # elif function_name == "get_company_news":
            #     result = get_financial_datasets_news(ticker, **kwargs)
            #     self.api_call_stats[APIProvider.FINANCIAL_DATASETS]["calls"] += 1
            #     return result
            # elif function_name == "get_insider_trades":
            #     result = get_financial_datasets_insider_trades(ticker, **kwargs)
            #     self.api_call_stats[APIProvider.FINANCIAL_DATASETS]["calls"] += 1
            #     return result
            else:
                # 对于暂时不支持的函数，返回空列表
                self.logger.warning(f"暂不支持的功能: {function_name}")
                return []
        except Exception as e:
            self.api_call_stats[APIProvider.FINANCIAL_DATASETS]["errors"] += 1
            raise

    def _try_fallback_financial_datasets(self, function_name: str, ticker: str, **kwargs) -> Any:
        """尝试使用FinancialDatasets作为降级方案"""
        self.logger.warning(f"API降级: {ticker} -> FinancialDatasets")
        try:
            return self._call_financial_datasets_api(function_name, ticker, **kwargs)
        except Exception as e:
            self.logger.error(f"降级API也失败了: {ticker} -> {e}")
            raise

    # A股数据获取方法（使用AKShare适配器）
    def _get_a_stock_prices(self, ticker: str, **kwargs) -> List[Price]:
        """获取A股价格数据"""
        try:
            self.api_call_stats[APIProvider.AKSHARE]["calls"] += 1
            return self.akshare_adapter.get_prices(ticker, **kwargs)
        except Exception as e:
            self.api_call_stats[APIProvider.AKSHARE]["errors"] += 1
            raise

    def _get_a_stock_metrics(self, ticker: str, **kwargs) -> List[FinancialMetrics]:
        """获取A股财务指标"""
        try:
            self.api_call_stats[APIProvider.AKSHARE]["calls"] += 1
            return self.akshare_adapter.get_financial_metrics(ticker, **kwargs)
        except Exception as e:
            self.api_call_stats[APIProvider.AKSHARE]["errors"] += 1
            raise

    def _get_a_stock_news(self, ticker: str, **kwargs) -> List[CompanyNews]:
        """获取A股新闻"""
        try:
            self.api_call_stats[APIProvider.AKSHARE]["calls"] += 1
            return self.akshare_adapter.get_company_news(ticker, **kwargs)
        except Exception as e:
            self.api_call_stats[APIProvider.AKSHARE]["errors"] += 1
            raise

    def _get_a_stock_insider_trades(self, ticker: str, **kwargs) -> List[InsiderTrade]:
        """获取A股内部交易"""
        try:
            self.api_call_stats[APIProvider.AKSHARE]["calls"] += 1
            return self.akshare_adapter.get_insider_trades(ticker, **kwargs)
        except Exception as e:
            self.api_call_stats[APIProvider.AKSHARE]["errors"] += 1
            raise

    # 加密货币数据获取方法（使用yfinance适配器）
    def _get_crypto_prices(self, ticker: str, **kwargs) -> List[Price]:
        """获取加密货币价格数据"""
        try:
            self.api_call_stats[APIProvider.YFINANCE]["calls"] += 1
            return self.yfinance_adapter.get_prices(ticker, **kwargs)
        except Exception as e:
            self.api_call_stats[APIProvider.YFINANCE]["errors"] += 1
            raise

    def _get_crypto_news(self, ticker: str, **kwargs) -> List[CompanyNews]:
        """获取加密货币新闻"""
        try:
            self.api_call_stats[APIProvider.YFINANCE]["calls"] += 1
            return self.yfinance_adapter.get_company_news(ticker, **kwargs)
        except Exception as e:
            self.api_call_stats[APIProvider.YFINANCE]["errors"] += 1
            raise

    def _log_api_call(self, asset_type: AssetType, ticker: str, function_name: str,
                     success: bool, response_time: float, error: Optional[str] = None):
        """记录API调用日志"""
        status = "成功" if success else "失败"
        api_name = TickerClassifier.get_api_name(asset_type)

        message = f"API调用 [{status}] {api_name}:{ticker} -> {function_name} ({response_time:.2f}s)"
        if error:
            message += f" 错误: {error}"

        if success:
            self.logger.info(message)
        else:
            self.logger.error(message)

    def get_api_stats(self) -> Dict[str, Any]:
        """获取API调用统计"""
        return {
            "call_stats": self.api_call_stats.copy(),
            "total_calls": sum(stats["calls"] for stats in self.api_call_stats.values()),
            "total_errors": sum(stats["errors"] for stats in self.api_call_stats.values()),
        }

    def reset_stats(self):
        """重置统计信息"""
        for stats in self.api_call_stats.values():
            stats["calls"] = 0
            stats["errors"] = 0


# 全局路由器实例
api_router = APIRouter()