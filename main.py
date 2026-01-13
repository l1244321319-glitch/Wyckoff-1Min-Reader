import os
import time
from datetime import datetime
import pandas as pd
import akshare as ak
import mplfinance as mpf
from openai import OpenAI

# ==========================================
# 1. 数据获取模块 (支持动态设置 BARS_COUNT)
# ==========================================

def get_symbol_with_prefix(symbol: str) -> str:
    """Akshare的分钟接口通常需要 sh/sz 前缀"""
    if symbol.startswith("6"):
        return f"sh{symbol}"
    elif symbol.startswith("0") or symbol.startswith("3"):
        return f"sz{symbol}"
    elif symbol.startswith("4") or symbol.startswith("8"):
        return f"bj{symbol}"
    return symbol

def fetch_a_share_minute(symbol: str) -> pd.DataFrame:
    """获取A股1分钟K线，数量由环境变量 BARS_COUNT 决定"""
    print(f"正在获取 {symbol} 的1分钟数据...")
    formatted_symbol = get_symbol_with_prefix(symbol)
    
    try:
        # period='1' 代表1分钟，adjust='qfq' 前复权
        df = ak.stock_zh_a_minute(
            symbol=formatted_symbol, 
            period="1", 
            adjust="qfq"
        )
    except Exception as e:
        print(f"获取失败，请检查股票代码格式或网络: {e}")
        return pd.DataFrame()

    # 统一列名
    rename_map = {
        "day": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    # 格式转换
    df["date"] = pd.to_datetime(df["date"])
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    
    # === 修改点：支持环境变量控制 K 线数量 (默认为 600) ===
    bars_count = int(os.getenv("BARS_COUNT", 600))
    df = df.sort_values("date").tail(bars_count).reset_index(drop=True)
    
    return df

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """添加威科夫分析所需的背景均线 (MA50/200)"""
    df = df.copy()
    # 在分钟级别，MA50和MA200代表短周期内的长期趋势线
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    return df

# ==========================================
# 2. 本地绘图模块 (增加错误捕获)
# ==========================================

def generate_local_chart(symbol: str, df: pd.DataFrame, save_path: str):
    """
    使用 mplfinance 在本地生成威科夫风格图表
    """
    if df.empty:
        return

    plot_df = df.copy()
    plot_df.set_index("date", inplace=True)

    # 设置样式
    mc = mpf.make_marketcolors(up='red', down='green', edge='i', wick='i', volume='in', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)

    # 添加均线图层
    apds = []
    if 'ma50' in plot_df.columns:
        apds.append(mpf.make_addplot(plot_df['ma50'], color='orange', width=1.0))
    if 'ma200' in plot_df.columns:
        apds.append(mpf.make_addplot(plot_df['ma200'], color='blue', width=1.2))

    try:
        # 绘图并保存
        mpf.plot(
            plot_df,
            type='candle',
            style=s,
            addplot=apds,
            volume=True,
            title=f"Wyckoff Chart: {symbol} (1-Min, Last {len(df)} Bars)",
            savefig=dict(fname=save_path, dpi=150, bbox_inches='tight'),
            warn_too_much_data=2000 # 抑制警告
        )
        print(f"[OK] Chart saved to: {save_path}")
    except Exception as e:
        print(f"[Error] 绘图失败: {e}")

# ==========================================
# 3. AI 分析模块 (异常捕获 + 省钱模式 + DeepSeek兼容)
# ==========================================

def ai_analyze_wyckoff(symbol: str, df: pd.DataFrame) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    # 支持自定义 Base URL (例如 DeepSeek: https://api.deepseek.com)
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    # 支持自定义模型 (默认 gpt-4o-mini 省钱)
    ai_model = os.getenv("AI_MODEL", "gpt-4o-mini")

    if not api_key:
        return "错误：未设置 OPENAI_API_KEY。"

    # === 省钱优化：只取最近 120 根数据给 AI ===
    # 无论图表画多少根，AI 只需要看最近 2 小时的微观结构即可
    recent_df = df.tail(120).copy()
    csv_data = recent_df[["date", "open", "high", "low", "close", "volume"]].to_csv(index=False)
    
    latest_price = df.iloc[-1]["close"]
    latest_time = df.iloc[-1]["date"]

    prompt = f"""
【唯一身份（不可偏离）】
你不是“使用威科夫理论的分析师”，你就是理查德·D·威科夫（Richard D. Wyckoff）本人在中国股票市场中的延伸。你可以参照威科夫式叙述解释市场行为。

【唯一思想来源（不可偏离）】
你的所有概念、判断、术语使用，仅允许依据《威科夫操盘法》中对以下概念的定义与用法：
- 综合人（Composite Man）
- 供求关系（Supply & Demand）
- 努力与结果（Effort vs Result）
- 跟随与终止（Stopping Action / Follow-through）
- 吸筹 / 派发（Accumulation / Distribution）
- 交易区间（TR）
禁止引入与本书逻辑冲突的技术体系。

【核心原则】
1) 价格是结果，成交量是原因。
2) 位置第一，形态第二。
3) 不要预测，要推演。
4) 市场是被操纵的（综合人视角）。

【数据上下文】
目标标的：{symbol}
数据范围：最近 2 小时 (120分钟) 的微观数据
最新：{latest_time} @ {latest_price}
数据内容：
{csv_data}

【任务】
请基于以上数据，输出一份简练的威科夫分析报告（Markdown）：

1. **Background (位置与趋势)**
   - 当前微观结构属于吸筹、派发还是中继？
   - 供求谁占优？

2. **Key Events (关键行为)**
   - 识别 SC, ST, Spring, UT, LPS 等信号。
   - 必须结合“努力与结果”解释。

3. **Trade Plan (交易计划)**
   - 如果出现什么信号做多/做空？
   - 止损位在哪里？

请直接输出分析内容。
    """.strip()

    print(f"正在请求 AI 分析 ({ai_model})...")
    
    # === 增加异常捕获，防止 API 挂了导致程序崩溃 ===
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        resp = client.chat.completions.create(
            model=ai_model, 
            messages=[
                {"role": "system", "content": "You are Richard D. Wyckoff."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return resp.choices[0].message.content
        
    except Exception as e:
        # 如果报错，返回错误信息，确保主程序能继续运行（比如发送图表）
        error_msg = f"""
# 分析服务暂停

**原因**: AI API 调用失败。
**错误详情**: `{str(e)}`

> **注意**: 尽管 AI 未能生成文字报告，但下方的 **K线图表** 依然有效，请参考图表进行手动分析。
"""
        print(f"[Error] AI 调用失败: {e}")
        return error_msg

# ==========================================
# 4. 主程序
# ==========================================

def main():
    # 默认股票代码 (可通过环境变量覆盖)
    symbol = os.getenv("SYMBOL", "600970") 
    
    # 1. 获取数据
    df = fetch_a_share_minute(symbol)
    if df.empty:
        print("未获取到数据，程序终止。")
        return
        
    df = add_indicators(df)

    # 建立输出目录
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("data", exist_ok=True)
    os.makedirs("reports", exist_ok=True)

    # 2. 保存CSV
    csv_path = f"data/{symbol}_1min_{ts}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[OK] CSV Saved: {csv_path} ({len(df)} rows)")

    # 3. 本地生成图表
    chart_path = f"reports/{symbol}_chart_{ts}.png"
    generate_local_chart(symbol, df, chart_path)

    # 4. 生成威科夫分析报告
    report_text = ai_analyze_wyckoff(symbol, df)

    # 5. 保存报告
    report_path = f"reports/{symbol}_report_{ts}.md"
    
    # 将图片链接插入 Markdown 报告顶部，方便查看
    final_report = f"![Wyckoff Chart](./{os.path.basename(chart_path)})\n\n{report_text}"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)

    print(f"[OK] Report Saved: {report_path}")

if __name__ == "__main__":
    main()
