# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码仓库中工作时提供指导。

## 项目概述

这是一个 AI 驱动的对冲基金系统，使用多个专业化的投资代理协同工作来制定交易决策。系统包含：

- **核心 Python 后端** (`src/`): 使用 LangGraph 协调投资决策的多代理系统
- **Web 应用程序** (`app/`): FastAPI 后端 + React 前端的可视化界面
- **回测引擎**: 全面的历史测试框架

## 开发命令

### Python 环境设置 (Poetry)
```bash
# 安装依赖
poetry install

# 激活虚拟环境
poetry shell

# 运行主要对冲基金命令行
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# 运行回测器
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

### Python 代码质量
```bash
# 格式化代码 (行长度: 420)
poetry run black src/ app/backend/

# 排序导入
poetry run isort src/ app/backend/

# 代码检查
poetry run flake8 src/ app/backend/

# 运行测试
poetry run pytest
```

### Web 应用程序开发
```bash
# 后端 (FastAPI)
cd app/backend
poetry run fastapi dev main.py

# 前端 (React + Vite)
cd app/frontend
npm run dev
npm run build
npm run lint
```

### 多API支持测试
```bash
# 测试ticker分类和路由功能
poetry run python test_multi_api.py

# 测试混合资产类型输入（新增功能！）
poetry run python src/main.py --ticker AAPL,CRYPTO.BTC,000001.SZ
poetry run python src/backtester.py --ticker AAPL,TSLA,CRYPTO.BTC,MSFT,000001.SZ
```

## 架构

### 多代理系统
系统使用 **18 个专业化代理** 进行协调工作流：

**投资传奇代理** (基于角色的投资风格):
- Warren Buffett, Charlie Munger, Ben Graham (价值投资)
- Cathie Wood, Bill Ackman, Stanley Druckenmiller (增长/激进投资)
- Peter Lynch, Phil Fisher, Michael Burry (专业策略)
- 以及其他代表著名投资哲学的代理

**技术分析代理**:
- `基本面代理`: 财务报表分析
- `技术面代理`: 价格/成交量技术指标
- `估值代理`: 内在价值计算 (DCF, 乘数)
- `情绪代理`: 市场情绪分析
- `新闻情绪代理`: 基于新闻的情绪分析
- `增长代理`: 增长指标和趋势

**管理层**:
- `风险管理器`: 头寸规模，投资组合风险指标
- `投资组合管理器`: 最终决策和订单生成

### 代理工作流
1. **数据收集**: 通过 API 工具获取金融数据
2. **并行分析**: 所有分析师代理同时处理相同数据
3. **风险评估**: 风险管理器评估每个推荐
4. **投资组合决策**: 投资组合管理器综合所有输入做出最终决策
5. **输出**: 带有推理和头寸规模的交易信号

### 关键组件

**状态管理** (`src/graph/state.py`):
- `AgentState`: 包含消息、数据和元数据的共享状态对象
- 使用 LangGraph 进行代理编排

**大语言模型集成** (`src/llm/`):
- 支持 OpenAI, Anthropic, Groq, DeepSeek, Ollama, Azure, Google Gemini
- 通过环境变量配置
- `src/utils/llm.py`: 大语言模型初始化工具

**数据源** (`src/data/`, `src/tools/api.py`):
- **多API智能路由系统**: 根据ticker类型自动选择最佳数据源
- **美股数据**: Financial Datasets API (AAPL, GOOGL, MSFT, NVDA, TSLA 免费)
- **A股数据**: AKShare API (免费开源，覆盖沪深交易所)
- **加密货币**: yfinance API (支持 BTC, ETH, SOL 等主流加密货币)
- **市场数据**: 价格、成交量、基本面、新闻情绪
- **智能缓存**: 性能优化的缓存层，支持API降级和故障转移

**回测引擎** (`src/backtesting/`):
- 具有现实约束的历史模拟
- 性能指标计算
- 基准比较
- 投资组合价值跟踪

### Web 应用程序架构

**后端** (`app/backend/`):
- FastAPI 配合 SQLAlchemy ORM
- PostgreSQL 数据库配合 Alembic 迁移
- 对冲基金操作的 RESTful API 端点
- 实时投资组合跟踪和回测结果

**前端** (`app/frontend/`):
- React 配合 TypeScript
- Vite 构建系统
- Tailwind CSS + shadcn/ui 组件
- React Flow 用于代理工作流可视化

## 配置

### 环境变量 (.env)
基本操作所需:
- `OPENAI_API_KEY` 或其他大语言模型提供商密钥
- `FINANCIAL_DATASETS_API_KEY` (用于非免费股票代码，美股数据源)

多API支持配置 (可选):
- `TUSHARE_TOKEN`: A股数据API密钥 (Tushare Pro，可选)
- `COINGECKO_API_KEY`: 加密货币数据API密钥 (可选，yfinance免费)
- `DATA_SOURCE_PRIORITIES`: 数据源优先级配置

### 代理配置
分析师代理在 `src/utils/analysts.py` 中配置:
- `ANALYST_CONFIG`: 所有代理的主配置
- `ANALYST_ORDER`: 执行顺序和工作流定义
- 通过修改此配置轻松添加/移除代理

## 关键模式

### 添加新代理
1. 在 `src/agents/new_agent.py` 中创建代理函数
2. 遵循标准代理签名: `def new_agent(state: AgentState) -> AgentState`
3. 添加到 `src/utils/analysts.py` 中的 `ANALYST_CONFIG`
4. 导入并包含在 `ANALYST_ORDER` 中

### 金融数据访问
- 使用 `src/tools/api.py` 函数进行智能数据访问（支持多API路由）
- 系统自动识别ticker类型并选择最佳数据源：
  - `AAPL` -> FinancialDatasets (美股)
  - `CRYPTO.BTC` -> yfinance (加密货币)
  - `000001.SZ` -> AKShare (A股)
- 支持混合输入: `--ticker AAPL,CRYPTO.BTC,000001.SZ`
- 统一的API接口，用户无需了解底层复杂性
- 智能缓存和API降级机制

### 多资产类型支持
- **美股**: 标准ticker格式 (AAPL, MSFT, NVDA)
- **加密货币**: CRYPTO.前缀格式 (CRYPTO.BTC, CRYPTO.ETH, CRYPTO.SOL)
- **A股**: 交易所后缀格式 (000001.SZ, 600000.SS, 688001.SH)
- **港股**: .HK后缀格式 (00700.HK)
- **混合使用**: 任意组合多种资产类型

### 错误处理
- 当 API 服务不可用时优雅降级
- 用户友好的错误消息，提供可操作的指导
- 瞬时故障的重试逻辑

### 数据库模式
- HedgeFundFlow: 存储单个分析结果
- HedgeFundFlowRun: 将相关分析分组到运行中
- HedgeFundFlowRunCycle: 跟踪执行周期
- API 密钥表用于管理凭据

## 开发注意事项

- 系统设计用于**教育目的** - 不进行实际交易
- 所有代理在相同数据上同时运行以获得多样化视角
- 投资组合决策来自共识和风险加权投票
- 回测提供现实的性能评估
- Web 界面使非技术用户能够访问系统

## 多API支持新增功能

- **🆕 A股支持**: 通过AKShare免费获取沪深交易所数据
- **🆕 加密货币支持**: 通过yfinance支持BTC、ETH、SOL等主流加密货币
- **🆕 混合资产**: 支持在单一命令中混合使用多种资产类型
- **🆕 智能路由**: 自动识别ticker格式并选择最佳数据源
- **🆕 降级机制**: API失败时自动切换到备用数据源
- **🆕 统一接口**: 完全向后兼容，现有用法不变

### 使用示例
```bash
# 原有方式继续有效
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# 新的混合支持
poetry run python src/main.py --ticker CRYPTO.BTC,CRYPTO.ETH,AAPL,000001.SZ
poetry run python src/backtester.py --ticker AAPL,TSLA,CRYPTO.BTC
```