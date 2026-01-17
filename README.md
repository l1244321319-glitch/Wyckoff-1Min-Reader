# 📈 Wyckoff-M1-Sentinel (威科夫 M1 哨兵)

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-green.svg)
![Strategy](https://img.shields.io/badge/Strategy-Wyckoff-orange.svg)
![AI Engine](https://img.shields.io/badge/AI-Gemini%20%7C%20GPT--4o-purple.svg)

> **拒绝情绪化交易，用代码还原市场真相。**
> 
> 一个基于 **GitHub Actions** 的全自动量化分析系统。它利用 **A股 1分钟微观数据**，结合 **AI 大模型 (Gemini/GPT-4o)** 进行 **威科夫 (Wyckoff)** 结构分析，并通过 **Telegram** 实现交互式监控与研报推送。

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
