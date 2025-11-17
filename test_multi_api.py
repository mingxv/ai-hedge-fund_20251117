#!/usr/bin/env python3
"""
多API功能测试脚本
测试A股和加密货币的ticker识别和路由功能
"""

import sys
import os
from datetime import datetime, date, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.ticker_classifier import TickerClassifier, AssetType


def test_ticker_classifier():
    """测试ticker分类器"""
    print("=== 测试Ticker分类器 ===")

    test_cases = [
        ("AAPL", AssetType.US_STOCK, "AAPL"),
        ("MSFT", AssetType.US_STOCK, "MSFT"),
        ("CRYPTO.BTC", AssetType.CRYPTO, "BTC"),
        ("CRYPTO.ETH", AssetType.CRYPTO, "ETH"),
        ("CRYPTO.SOL", AssetType.CRYPTO, "SOL"),
        ("000001.SZ", AssetType.A_STOCK, "000001.SZ"),
        ("600000.SS", AssetType.A_STOCK, "600000.SS"),
        ("00700.HK", AssetType.HK_STOCK, "00700.HK"),
        ("INVALID.TICKER", AssetType.UNKNOWN, "INVALID.TICKER"),
        ("", AssetType.UNKNOWN, ""),
    ]

    for ticker, expected_type, expected_normalized in test_cases:
        try:
            asset_type, normalized = TickerClassifier.classify(ticker)
            status = "✅" if (asset_type == expected_type and normalized == expected_normalized) else "❌"
            print(f"{status} {ticker:<15} -> {asset_type.value:<10} ({normalized})")
            if asset_type != expected_type:
                print(f"   期望: {expected_type.value}, 实际: {asset_type.value}")
            if normalized != expected_normalized:
                print(f"   期望: '{expected_normalized}', 实际: '{normalized}'")
        except Exception as e:
            print(f"❌ {ticker:<15} -> 错误: {e}")

    print()


def test_api_router_basic():
    """测试API路由器基本功能"""
    print("=== 测试API路由器基本功能 ===")

    try:
        from src.utils.api_router import api_router

        # 测试混合ticker输入
        mixed_tickers = ["AAPL", "CRYPTO.BTC", "000001.SZ", "MSFT"]

        print(f"测试混合ticker: {mixed_tickers}")

        for ticker in mixed_tickers:
            asset_type, normalized = TickerClassifier.classify(ticker)
            api_name = TickerClassifier.get_api_name(asset_type)
            print(f"  {ticker:<15} -> {asset_type.value:<10} (使用 {api_name})")

        print("✅ API路由器基本功能测试通过")
        print()

    except Exception as e:
        print(f"❌ API路由器测试失败: {e}")
        print()


def test_api_integration():
    """测试API集成（需要API密钥）"""
    print("=== 测试API集成 ===")

    # 检查是否有API密钥
    financial_datasets_key = os.environ.get("FINANCIAL_DATASETS_API_KEY")

    if not financial_datasets_key:
        print("⚠️  未设置 FINANCIAL_DATASETS_API_KEY，跳过API集成测试")
        print("  请设置环境变量或创建 .env 文件进行完整测试")
        print()
        return

    try:
        from src.tools.api import get_prices

        # 测试日期范围（最近30天）
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        # 测试用例：美股（应该使用FinancialDatasets）
        print("测试美股数据获取...")
        try:
            us_prices = get_prices("AAPL", start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            print(f"✅ 美股 AAPL: 获取到 {len(us_prices)} 条价格数据")
        except Exception as e:
            print(f"❌ 美股 AAPL 获取失败: {e}")

        # 测试用例：A股（应该使用AKShare）
        print("测试A股数据获取...")
        try:
            a_prices = get_prices("000001.SZ", start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            print(f"✅ A股 000001.SZ: 获取到 {len(a_prices)} 条价格数据")
        except Exception as e:
            print(f"❌ A股 000001.SZ 获取失败: {e}")

        # 测试用例：加密货币（应该使用yfinance）
        print("测试加密货币数据获取...")
        try:
            crypto_prices = get_prices("CRYPTO.BTC", start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            print(f"✅ 加密货币 BTC: 获取到 {len(crypto_prices)} 条价格数据")
        except Exception as e:
            print(f"❌ 加密货币 BTC 获取失败: {e}")

        print()

    except Exception as e:
        print(f"❌ API集成测试失败: {e}")
        print()


def test_mixed_ticker_command():
    """测试混合ticker命令行格式"""
    print("=== 测试混合ticker命令格式 ===")

    # 模拟命令行输入
    test_commands = [
        "AAPL,MSFT,NVDA",  # 仅美股
        "CRYPTO.BTC,CRYPTO.ETH,CRYPTO.SOL",  # 仅加密货币
        "000001.SZ,600000.SS,688001.SH",  # 仅A股
        "AAPL,CRYPTO.BTC,000001.SZ,MSFT",  # 混合
        "AAPL,TSLA,CRYPTO.ETH,00700.HK",  # 更复杂的混合
    ]

    for cmd in test_commands:
        tickers = [t.strip() for t in cmd.split(",") if t.strip()]
        print(f"命令: --ticker {cmd}")

        asset_counts = {}
        for ticker in tickers:
            asset_type, _ = TickerClassifier.classify(ticker)
            asset_name = TickerClassifier.get_display_name(asset_type)
            asset_counts[asset_name] = asset_counts.get(asset_name, 0) + 1

        for asset_name, count in asset_counts.items():
            print(f"  {asset_name}: {count} 个")
        print()


def main():
    """主测试函数"""
    print("AI Hedge Fund 多API支持测试")
    print("=" * 50)
    print()

    # 运行各项测试
    test_ticker_classifier()
    test_api_router_basic()
    test_api_integration()
    test_mixed_ticker_command()

    print("测试完成！")
    print("=" * 50)

    # 显示使用示例
    print("\n📋 使用示例:")
    print("poetry run python src/main.py --ticker AAPL,MSFT,NVDA")
    print("poetry run python src/main.py --ticker CRYPTO.BTC,CRYPTO.ETH,AAPL")
    print("poetry run python src/main.py --ticker 000001.SZ,600000.SS,CRYPTO.SOL")
    print("poetry run python src/backtester.py --ticker AAPL,TSLA,CRYPTO.BTC")


if __name__ == "__main__":
    main()