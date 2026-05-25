# IBKR Trade Analyzer

[![版本](https://img.shields.io/badge/版本-2.0.0-blue)](https://github.com/Esonhugh/Marketplace/tree/Skyworship/plugins/ibkr-trade-analyzer)
[![许可证](https://img.shields.io/badge/许可证-MIT-green)](LICENSE)

**一个用于分析 Interactive Brokers 交易历史的 Claude Code 与 Codex 插件 — 只读分析，零风险。**

## 功能介绍

本插件通过 IBKR 的只读 Flex Web Service API 连接你的账户，或读取本地导出的 CSV/XML 文件，生成全面的交易分析报告：

| 维度 | 详细内容 |
|------|---------|
| **交易行为模式** | 交易频率、持仓周期、时段分布、胜率、盈亏比 |
| **盈亏表现** | 已实现盈亏、权益曲线、夏普比率、最大回撤、月度收益 |
| **组合结构** | 资产配置、行业集中度、多空比例、仓位大小 |
| **成本基准（三种方法）** | 保本价/摊薄成本（富途算法）、FIFO 先进先出、LIFO 后进先出 — 三种方法并列对比 |
| **费用与现金流** | 佣金、利息、股息、融资成本、费用/盈亏比 |
| **现金与外汇** | 多币种余额、外汇汇率（1 USD = X 外币）、流动性比率 |
| **交易风格画像** | 自动生成的定性总结（日内/波段/趋势、方向偏好、风险偏好）|
| **风险评估** | 6 个维度的 0-100 评分，附具体风险预警 |
| **价格图表** | 叠加买卖标记的历史价格走势图 |

### v2.0.0 新特性

- **Claude Code 插件清单** — 当前 checkout 包含 Claude Code 插件清单 (`.claude-plugin/plugin.json`)
- **可选 Codex packaging** — Codex 清单 (`.codex-plugin/plugin.json`)、marketplace 元数据 (`.agents/plugins/marketplace.json`) 和 Codex MCP 配置 (`.codex-mcp.json`) 属于可选 packaging surface，当前 checkout 未包含这些文件
- **宿主 MCP 启动路径** — Claude 继续使用 `.mcp.json`；包含 Codex packaging 的分发包可通过 `.codex-mcp.json` 复用同一个 MCP 服务端
- **宿主感知缓存** — 优先使用插件宿主提供的数据目录，本地开发回退到 `cache/`

### v1.2.0

- **保本价/摊薄成本（富途算法）** — 计算每只标的的动态保本价：盈利卖出降低剩余持仓成本，亏损卖出抬高成本。佣金单独记录，不计入成本价（与富途/moomoo 一致）
- **LIFO 后进先出** — 新增 LIFO 成本基准分析器，优先匹配最近买入的份额（IBKR 税务优化器的 7 种方法之一）
- **三种方法并列对比** — 报告中保本价 vs FIFO vs LIFO 逐标的对比展示
- **单标的深度分析** — `--symbol AMZN,BRK B` 参数生成逐笔交易的成本演变详情
- **`diluted_cost` 分析板块** — 新增 `--analyzers diluted_cost` 选项；默认全量运行时自动包含

## 安装

### 方式一：Claude Code Marketplace

首先，将本仓库添加为 marketplace 源：

```claude
/plugin marketplace add Esonhugh/Marketplace
```

然后安装插件：

```claude
/plugin install ibkr-trade-analyzer
```

或使用 `claude` CLI：

```bash
claude plugin marketplace add Esonhugh/Marketplace
claude plugin install ibkr-trade-analyzer
```

### 方式二：Codex 本地 Marketplace

Codex packaging 是可选内容，并非每个 checkout 都包含。当前 checkout 未包含 `.codex-plugin/plugin.json`、`.agents/plugins/marketplace.json` 和 `.codex-mcp.json`；只有在使用包含这些文件的分发包时才使用此方式。

在本插件根目录执行：

```bash
codex plugin marketplace add "$(pwd)"
```

然后打开 Codex，在 `/plugins` 中安装 `ibkr-trade-analyzer`。

Codex 不读取 Claude `userConfig`，请在启动 Codex 的 shell 中设置凭证：

```bash
export IBKR_FLEX_TOKEN="your-token-here"
export IBKR_QUERY_ID="123456"
export PROXY=""  # 可选
codex
```

### 方式三：从 GitHub 克隆

克隆整个 marketplace 仓库，并指定插件目录：

```bash
git clone https://github.com/Esonhugh/Marketplace.git
claude --plugin-dir ./Marketplace/plugins/ibkr-trade-analyzer
```

或仅克隆插件到插件目录：

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/Esonhugh/Marketplace.git /tmp/marketplace
cd /tmp/marketplace && git sparse-checkout set plugins/ibkr-trade-analyzer
cp -r plugins/ibkr-trade-analyzer ~/.claude/plugins/ibkr-trade-analyzer
```

## 使用方法

安装后，直接对 Claude 或 Codex 说：

```
分析我的 IBKR 交易历史
```

助手会引导你完成：

1. **选择数据来源** — Flex Web Service（在线）或本地文件（离线）
2. **提供凭证** — Flex Token + Query ID，或文件路径
3. **运行分析** — 自动执行，生成 Markdown + 交互式 HTML 报告
4. **查看结果** — 与 Claude 交互讨论分析发现

### 工作流命令

插件也提供面向常见复盘场景的命令式工作流：

| 命令 | 适用场景 | 主要工具 |
|------|----------|----------|
| `/ibkr-trade-analyzer:summary` | 一页纸账户摘要 | `ibkr_pnl_summary`, `ibkr_portfolio`, `ibkr_cost_analysis` |
| `/ibkr-trade-analyzer:portfolio` | 持仓、仓位、集中度、配置比例 | `ibkr_portfolio` |
| `/ibkr-trade-analyzer:cash-fx` | 现金余额、币种敞口、换汇观察 | `ibkr_portfolio`, `ibkr_fx_analysis`, `ibkr_cost_analysis` |
| `/ibkr-trade-analyzer:report` | 生成 Markdown 和 HTML 完整报告 | `ibkr_generate_report` |
| `/ibkr-trade-analyzer:analyze` | 带时间或资产类型过滤的定向分析 | `ibkr_analyze` |

现金换汇和仓位输出仅供信息分析参考，不会下单、不会换汇，也不构成投资或税务建议。

### 选择性分析

使用 `--analyzers` 仅运行指定板块：

```bash
# 仅盈亏深度分析
uv run ibkr_analyzer.py --mode flex --analyzers pnl,trade

# 仅外汇成本分析（不拉取价格数据）
uv run ibkr_analyzer.py --mode file --source activity.xml --analyzers fx --no-prices

# 仅组合快照
uv run ibkr_analyzer.py --mode flex --analyzers portfolio --no-prices
```

可用 `--analyzers` 板块：`trade`、`pnl`、`portfolio`、`cost`、`price`、`fx`、`diluted_cost`（独立 CLI）以及 `china_tax`（MCP `ibkr_analyze`）。

## 数据来源

### 方式 A：Flex Web Service（推荐）

从 IBKR 的只读报告 API 直接拉取数据。

**设置步骤：**
1. 登录 [IBKR 账户管理](https://www.interactivebrokers.com/sso/Login)
2. 进入 **Performance & Reports > Flex Queries**
3. 创建新的 Activity Flex Query，勾选：**Trades、Cash Transactions、Open Positions、Account Information**
4. 输出格式设为 **XML**，保存后记录 **Query ID**
5. 在 **Manage Flex Web Service** 中获取 **Flex Token**

**Claude 插件配置：** 安装时会自动提示输入凭证：

```bash
/plugin install ibkr-trade-analyzer
```

Claude Code 会提示你输入 Flex Token（加密存入系统 keychain）和 Query ID。之后每次运行自动注入，无需任何文件管理。

**Codex 或脚本配置** — Codex 启动内置 MCP 服务端时会继承环境变量：

```bash
export IBKR_FLEX_TOKEN="your-token-here"
export IBKR_QUERY_ID="123456"
export PROXY="socks5://127.0.0.1:7980"  # 可选
```

### 方式 B：本地文件

从 IBKR Client Portal 或 TWS 导出文件，提供文件路径即可。支持 CSV 和 XML 格式。

- **Client Portal**：Performance & Reports → Statements → Activity → Download（推荐 XML 格式）
- **TWS**：Account → Account Window → Export

直接运行脚本的示例命令：
```bash
uv run ibkr_analyzer.py --mode file --source ~/Downloads/activity.xml --output reports/
```

## 配置

Claude 凭证在安装时由 Claude Code 的内置插件设置系统提示输入；Codex 凭证从启动 Codex 进程的环境变量读取。Claude 安装命令：

```claude
/plugin install ibkr-trade-analyzer
```

| 字段 | 是否加密 | 说明 |
|------|----------|------|
| `flex_token` | 是 — 存入系统 keychain | Flex Web Service token |
| `query_id` | 否 — 存入 settings.json | Flex Query 数字 ID |
| `proxy` | 否 | 代理地址，如 `socks5://127.0.0.1:7980`，留空自动读取 `ALL_PROXY` / `HTTPS_PROXY` |

## 输出

报告保存在 `reports/` 目录下：
- `ibkr-analysis-YYYY-MM-DD.md` — 完整 Markdown 报告（含表格）
- `ibkr-analysis-YYYY-MM-DD.html` — 交互式 HTML 报告（含 Plotly 图表）

Flex XML 响应会缓存到插件宿主数据目录（`$PLUGIN_DATA/cache` 或 `$CLAUDE_PLUGIN_DATA/cache`），本地开发回退到 `cache/`。当天再次运行时自动读取缓存，无需重新调用 API。

## 安全保证

本插件以**只读安全**为核心设计原则：

1. **API 层面** — Flex Web Service 不存在任何写入/下单接口
2. **代码层面** — 未导入任何交易执行库（无 `ibapi`、无 `ib_insync`）
3. **网络层面** — 仅向 IBKR Flex 报告端点发起出站 HTTPS 请求
4. **文件层面** — 仅写入 `reports/` 输出目录

## 环境要求

- Python >= 3.10
- `uv` — 用于隔离运行脚本，不污染系统 Python 环境。安装：`curl -LsSf https://astral.sh/uv/install.sh | sh`
- 依赖通过 [PEP 723](https://peps.python.org/pep-0723/) 内联元数据由 `uv run` 自动安装，无需手动配置 venv

## 许可证

MIT

## 作者

[Esonhugh](https://github.com/Esonhugh) — [插件主页](https://github.com/Esonhugh/Marketplace/tree/Skyworship/plugins/ibkr-trade-analyzer)
