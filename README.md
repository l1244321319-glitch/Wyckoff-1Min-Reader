# 📈 Wyckoff-M1-Sentinel (威科夫 M1 哨兵)

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-green.svg)
![Strategy](https://img.shields.io/badge/Strategy-Wyckoff-orange.svg)
![AI Engine](https://img.shields.io/badge/AI-Gemini%20%7C%20GPT--4o-purple.svg)

> **拒绝情绪化交易，用代码还原市场真相。**
> 
> 一个基于 **GitHub Actions** 的全自动量化分析系统。它利用 **A股 1分钟微观数据**，结合 **AI 大模型 (Gemini/GPT-4o)** 进行 **威科夫 (Wyckoff)** 结构分析，并通过 **Telegram** 实现交互式监控与研报推送。

# 📅 本周更新日志 (Weekly Update Changelog)

> **版本摘要**：本周重点重构了数据获取引擎，解决了历史数据不足的问题；构建了“三级 AI 熔断兜底”机制提升稳定性；同时升级了 **Google Sheet 适配器**，支持在表格中直接定义每只股票的分析周期和数据长度。

## 🚀 核心功能升级 (Core Features)

### 1. Google Sheet 适配升级 (Sheet Integration)
`SheetManager` 模块进行了底层重构，支持动态读取表格的扩展列，实现了“千股千策”的配置能力。

- **动态配置读取**：新增对表格 **第 5 列 (Timeframe)** 和 **第 6 列 (Bars)** 的读取支持。
- **向下兼容设计**：如果表格中未填写这两列，程序会自动应用默认值（5分钟周期 / 500根 K 线），无需担心旧版表格报错。
- **配置热更新**：无需修改代码，直接在 Google Sheet 修改数值，下次运行 Actions 时即可生效（例如将某只股票改为 60分钟级别）。

### 2. 双源数据引擎 (Hybrid Data Engine)
为了解决 AkShare 历史数据长度不足的问题，我们引入了 **BaoStock** 作为历史数据源。

- **混合模式**：自动合并 `BaoStock` (历史长周期) + `AkShare` (实时/近期补全) 的数据。
- **1分钟级特判**：针对 1 分钟级别数据，自动切换为 AkShare 全量抓取模式（因 BaoStock 不支持 1 分钟）。
- **智能清洗与对齐**：
    - **时间戳修复**：自动解析 BaoStock 的非标准时间格式。
    - **单位自动对齐**：智能检测并修复“手”与“股”之间的 100 倍数量级差异，防止量能指标（Volume）失真。
    - **索引冲突修复**：修复了合并数据时出现的 `Reindexing only valid with uniquely valued Index objects` 错误。

### 3. 三级 AI 兜底策略 (Triple-Tier AI Fallback)
构建了多级容错链，应对官方接口频繁的 `429` (限流) 和 `503` (过载) 错误：

1.  **第一优先级**：Google 官方 Gemini API (`gemini-3-flash-preview`)。
2.  **第二优先级**：自定义中转 API (`api2.qiandao.mom` / `gemini-3-pro-preview-h`)。
3.  **最终防线**：OpenAI / DeepSeek (`gpt-4o` 兼容接口)。

> **策略优化**：采用“快速失败”策略（仅重试 1 次），遇到错误立即切换下一级，确保分析报告 100% 生成。

### 4. 连接稳定性增强 (Connectivity)
- **防断连**：HTTP Header 添加伪装 `User-Agent` 并强制 `Connection: close`，防止 TCP 连接复用导致的 `RemoteDisconnected` 错误。
- **致命错误熔断**：遇到 `400` (Key 无效) 等错误直接中断重试。
- **超时调整**：超时时间延长至 **120秒**，适应 Gemini 3.0 的思考时间。

---

## 🛠️ 配置变更指南 (Configuration Guide)

### 1. Google Sheets 表格结构变更
建议在您的表格头行（第一行）新增 **Timeframe** 和 **Bars** 标题，并在对应列填写参数：

| 列号 | 标题 | 说明 | 示例值 |
| :--- | :--- | :--- | :--- |
| **A** | Symbol | 股票代码 | `600519` |
| **B** | Date | 持仓日期 | `2023-01-01` |
| **C** | Price | 持仓价格 | `1500` |
| **D** | Qty | 持仓数量 | `100` |
| **E** | **Timeframe** | **[新增] 分析周期 (分钟)** | `1`, `5`, `15`, `30`, `60` |
| **F** | **Bars** | **[新增] K线抓取数量** | `500`, `1000`, `2000` |

> *注：E、F 列留空则默认使用 `5m` 和 `500`。*

### 2. GitHub Secrets 新增
请前往仓库 Settings -> Secrets 添加：

- `CUSTOM_API_KEY`: **[必需]** 第三方中转 API 的 Key。

### 3. Workflow 策略
- **强制冷却**：每只股票分析间隔调整为 **30秒**。

---

## ✨ 核心功能 (Key Features)

* **🕵️‍♂️ 1分钟微观哨兵**：自动抓取 A 股 **1分钟 K 线**数据，捕捉肉眼难以察觉的主力吸筹/派发痕迹。
* **🧠 双引擎 AI 分析**：
    * **主引擎**：Google Gemini Pro (高速、免费)
    * **副引擎**：OpenAI GPT-4o (精准、兜底)
    * 深度分析供求关系，自动识别 Spring (弹簧效应)、UT (上冲回落)、LPS (最后支撑点) 等威科夫关键行为。
* **🤖 交互式 Telegram 机器人**：
    * **指令管理**：直接在电报群发送代码即可添加/删除监控，无需接触代码。
    * **研报推送**：自动生成包含红绿高对比 K 线图的 **PDF 研报**，推送到手机。
* **☁️ Serverless 架构**：完全运行在 GitHub Actions 上，**无需服务器，零成本维护**。
* **⏰ 智能调度**：
    * **午盘 (12:00)** & **收盘 (15:15)**：自动运行分析并推送报告。
    * **每 30 分钟**：自动同步 Telegram 指令，更新监控列表。


---
## 🏗️ 系统架构

```mermaid
graph TD
    User(("👨‍💻 用户")) <-->|"指令交互 / 接收 PDF"| TG["Telegram Bot"]
    TG <-->|"每30分钟同步"| GH["GitHub Actions (Monitor)"]
    GH <-->|"读写"| LIST["stock_list.txt"]
    
    LIST -->|"读取列表"| JOB["GitHub Actions (Daily Report)"]
    JOB -->|"1. 获取数据"| API["AkShare 财经接口"]
    JOB -->|"2. 绘制图表"| PLOT["Mplfinance"]
    JOB -->|"3. AI推理"| AI["Gemini / GPT-4o"]
    JOB -->|"4. 生成PDF"| PDF["Report.pdf"]
    PDF -->|"推送"| TG
