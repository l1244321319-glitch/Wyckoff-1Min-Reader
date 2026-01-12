import os
from datetime import datetime
import pandas as pd
import akshare as ak
from openai import OpenAI


def fetch_a_share_daily(symbol: str) -> pd.DataFrame:
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date="20150101",
        end_date=datetime.now().strftime("%Y%m%d"),
        adjust="qfq",
    )
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "涨跌幅": "pct_chg",
        "换手率": "turnover",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    if "volume" in df.columns:
        df["vma20"] = df["volume"].rolling(20).mean()
    return df


def ai_analyze(symbol: str, df: pd.DataFrame) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "未设置 OPENAI_API_KEY（GitHub Secrets）。本次仅生成CSV与占位报告。"

    client = OpenAI(api_key=api_key)

    tail = df.tail(260).copy()  # 约1年交易日
    latest = tail.iloc[-1].to_dict()

    compact = tail[["date", "open", "high", "low", "close", "volume", "ma20", "ma50", "ma200"]].copy()
    compact["date"] = compact["date"].dt.strftime("%Y-%m-%d")
    csv_preview = compact.tail(80).to_csv(index=False)

    prompt = f"""
你是一名严谨的股票研究员。请基于以下日线行情与均线指标，对A股 {symbol} 输出一份可执行的分析报告（Markdown）。
要求：
1) 结论摘要：当前趋势、关键位、核心风险（3-6条）
2) 技术面：趋势结构、支撑阻力、量价、均线（MA20/50/200）、强弱信号
3) 未来3种剧本：上行/震荡/下行，每种给触发条件与验证/失效条件
4) 交易计划：入场条件、止损、止盈、仓位、风险控制
5) 同时补充基本面框架：行业景气、公司业务/盈利质量、估值与风险点（不需要查外网，用框架+根据价格行为做合理假设并标注“假设”）
6) 声明：历史数据分析不构成投资建议。

最新一根数据（含指标）：
{latest}

最近80根数据（CSV）：
{csv_preview}
""".strip()

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )
    return resp.output_text


def main():
    symbol = os.getenv("SYMBOL", "600970")  # 可通过环境变量覆盖
    df = fetch_a_share_daily(symbol)
    df = add_indicators(df)

    # 保存CSV（本地/Action运行时会生成，但默认不提交）
    os.makedirs("data", exist_ok=True)
    csv_path = f"data/{symbol}_daily.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 生成报告（提交到仓库）
    os.makedirs("reports", exist_ok=True)
    report_text = ai_analyze(symbol, df)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"reports/{symbol}_report_{ts}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"[OK] CSV: {csv_path} rows={len(df)}")
    print(f"[OK] Report: {report_path}")


if __name__ == "__main__":
    main()
