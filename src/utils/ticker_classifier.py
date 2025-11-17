"""Ticker分类和识别模块，支持多种资产类型的智能识别"""

from enum import Enum
from typing import Tuple, Optional
import re


class AssetType(Enum):
    """资产类型枚举"""
    US_STOCK = "us_stock"      # 美股
    A_STOCK = "a_stock"        # A股
    HK_STOCK = "hk_stock"      # 港股
    CRYPTO = "crypto"          # 加密货币
    UNKNOWN = "unknown"        # 未知类型


class TickerClassifier:
    """Ticker分类器，用于识别不同类型的金融资产"""

    # A股交易所后缀
    A_STOCK_SUFFIXES = {'.SZ', '.SS', '.SH', '.BJ'}

    # 常见加密货币符号（用于额外验证）
    COMMON_CRYPTO_SYMBOLS = {
        'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'DOT', 'MATIC', 'LINK',
        'UNI', 'LTC', 'BCH', 'AVAX', 'ATOM', 'FIL', 'TRX', 'ETC', 'VET', 'THETA',
        'ICP', 'XLM', 'NEAR', 'ALGO', 'MANA', 'SAND', 'AXS', 'AAVE', 'COMP', 'MKR'
    }

    @classmethod
    def classify(cls, ticker: str) -> Tuple[AssetType, str]:
        """
        识别ticker类型并标准化格式

        Args:
            ticker: 原始ticker字符串

        Returns:
            Tuple[AssetType, str]: (资产类型, 标准化ticker)
        """
        if not ticker:
            return AssetType.UNKNOWN, ""

        original_ticker = ticker.strip()
        ticker = original_ticker.upper()

        # 1. 常见加密货币符号（直接识别）
        if ticker in cls.COMMON_CRYPTO_SYMBOLS:
            return AssetType.CRYPTO, ticker

        # 2. 加密货币：CRYPTO.BTC, CRYPTO.ETH 格式
        if ticker.startswith('CRYPTO.'):
            symbol = ticker[7:]  # 移除'CRYPTO.'前缀（注意是7个字符）
            if cls._is_valid_crypto_symbol(symbol):
                return AssetType.CRYPTO, symbol
            else:
                # 即使不在常见列表中，只要是CRYPTO.开头的也认为是加密货币
                return AssetType.CRYPTO, symbol

        # 2. A股：检查交易所后缀
        for suffix in cls.A_STOCK_SUFFIXES:
            if ticker.endswith(suffix):
                # 验证股票代码格式
                code = ticker[:-3]  # 移除后缀
                if cls._is_valid_a_stock_code(code):
                    return AssetType.A_STOCK, ticker
                else:
                    return AssetType.UNKNOWN, original_ticker

        # 3. 港股：.HK 后缀
        if ticker.endswith('.HK'):
            code = ticker[:-3]  # 移除后缀
            if cls._is_valid_hk_stock_code(code):
                return AssetType.HK_STOCK, ticker
            else:
                return AssetType.UNKNOWN, original_ticker

        # 4. 美股：1-5个字母，无后缀
        if re.match(r'^[A-Z]{1,5}$', ticker):
            # 排除一些明显不是美股的情况
            if not cls._is_excluded_symbol(ticker):
                return AssetType.US_STOCK, ticker

        # 5. 默认为未知类型
        return AssetType.UNKNOWN, original_ticker

    @classmethod
    def _is_valid_crypto_symbol(cls, symbol: str) -> bool:
        """验证是否为有效的加密货币符号"""
        if not symbol or len(symbol) < 2 or len(symbol) > 10:
            return False

        # 检查是否只包含字母
        if not re.match(r'^[A-Z]+$', symbol):
            return False

        # 检查是否在常见加密货币列表中，或者以合理的模式存在
        return (symbol in cls.COMMON_CRYPTO_SYMBOLS or
                re.match(r'^[A-Z]{2,5}$', symbol))

    @classmethod
    def _is_valid_a_stock_code(cls, code: str) -> bool:
        """验证是否为有效的A股代码"""
        if not code or not code.isdigit():
            return False

        code_num = int(code)

        # A股代码规则：
        # 000xxx: 深圳主板
        # 001xxx: 深圳主板新股
        # 002xxx: 深圳中小板
        # 003xxx: 深圳主板新股
        # 300xxx: 深圳创业板
        # 600xxx, 601xxx, 603xxx, 605xxx: 上海主板
        # 688xxx: 上海科创板
        # 8xxxxx: 北交所
        # 430xxx: 北交所
        return (
            (000000 <= code_num <= 999999 and
             (code.startswith('000') or code.startswith('001') or
              code.startswith('002') or code.startswith('003') or
              code.startswith('300') or code.startswith('600') or
              code.startswith('601') or code.startswith('603') or
              code.startswith('605') or code.startswith('688'))) or
            (code.startswith('8') and len(code) == 6) or
            (code.startswith('43') and len(code) == 6)
        )

    @classmethod
    def _is_valid_hk_stock_code(cls, code: str) -> bool:
        """验证是否为有效的港股代码"""
        if not code or not code.isdigit():
            return False

        # 港股代码通常是5位数字
        return len(code) == 5 and code.isdigit()

    @classmethod
    def _is_excluded_symbol(cls, symbol: str) -> bool:
        """排除一些明显不是美股的符号"""
        # 排除一些常见的错误输入或特殊符号
        excluded = {
            'TEST', 'DEMO', 'NULL', 'UNKN', 'UNKNOWN', 'EXAMPLE',
            'AAPL1', 'MSFT2', 'TSLA3'  # 带数字的情况
        }

        # 如果包含数字，可能是错误的输入
        if any(c.isdigit() for c in symbol):
            return True

        return symbol in excluded

    @classmethod
    def get_display_name(cls, asset_type: AssetType) -> str:
        """获取资产类型的显示名称"""
        display_names = {
            AssetType.US_STOCK: "美股",
            AssetType.A_STOCK: "A股",
            AssetType.HK_STOCK: "港股",
            AssetType.CRYPTO: "加密货币",
            AssetType.UNKNOWN: "未知类型"
        }
        return display_names.get(asset_type, "未知类型")

    @classmethod
    def get_api_name(cls, asset_type: AssetType) -> str:
        """获取资产类型对应的API名称"""
        api_names = {
            AssetType.US_STOCK: "FinancialDatasets",
            AssetType.A_STOCK: "AKShare",
            AssetType.CRYPTO: "yfinance",
            AssetType.HK_STOCK: "FinancialDatasets",
            AssetType.UNKNOWN: "Unknown"
        }
        return api_names.get(asset_type, "Unknown")