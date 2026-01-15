import os
import time
import json
import requests
from datetime import datetime
import pandas as pd
import akshare as ak
import mplfinance as mpf
from openai import OpenAI
import numpy as np
import markdown
from xhtml2pdf import pisa  # 用于生成 PDF

# ==========================================
# 1. 数据获取模块
# ==========================================

def fetch_a_share_minute(symbol: str) -> pd.DataFrame:
    symbol_code = ''.join(filter(str.isdigit, symbol))
    print(f"正在获取 {symbol_code} 的1分钟数据 (Source: Eastmoney)...")

    try:
        df = ak.stock_zh_a_hist_min_em(symbol=symbol_code, period="1", adjust="qfq")
    except Exception as e:
        print(f"获取失败: {e}")
        return pd.DataFrame()

    if df.empty: return pd.DataFrame()

    rename_map = {"时间": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    df["date"] = pd.to_datetime(df["date"])
    cols = ["open", "high", "low", "close", "volume"]
    df[cols] = df[cols].astype(float)
    
    # === Open=0 修复逻辑 ===
    if (df["open"] == 0).any():
        print(f"   [数据清洗] 修复 Open=0 数据...")
        df["open"] = df["open"].replace(0, np.nan)
        df["open"] = df["open"].fillna(df["close"].shift(1))
        df["open"] = df["open"].fillna(df["close"])

    bars_count = int(os.getenv("BARS_COUNT", 600))
    df = df.sort_values("date").tail(bars_count).reset_index(drop=True)
    return df

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    return df

# ==========================================
# 2. 本地绘图模块 (专业版)
# ==========================================

def generate_local_chart(symbol: str, df: pd.DataFrame, save_path: str):
    if df.empty: return

    plot_df = df.copy()
    plot_df.set_index("date", inplace=True)

    mc = mpf.make_marketcolors(
        up='#ff3333', down='#00b060', 
        edge='inherit', wick='inherit', 
        volume={'up': '#ff3333', 'down': '#00b060'},
        inherit=True
    )
    s = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc, gridstyle=':', y_on_right=True)

    apds = []
    if 'ma50' in plot_df.columns:
        apds.append(mpf.make_addplot(plot_df['ma50'], color='#ff9900', width=1.5))
    if 'ma200' in plot_df.columns:
        apds.append(mpf.make_addplot(plot_df['ma200'], color='#2196f3', width=2.0))

    try:
        mpf.plot(
            plot_df, type='candle', style=s, addplot=apds, volume=True,
            title=f"Wyckoff Setup: {symbol}",
            savefig=dict(fname=save_path, dpi=150, bbox_inches='tight'),
            warn_too_much_data=2000
        )
        print(f"[OK] Chart saved to: {save_path}")
    except Exception as e:
        print(f"[Error] 绘图失败: {e}")

# ==========================================
# 3. AI 分析模块
# ==========================================

def get_prompt_content(symbol, df):
    prompt_template = os.getenv("WYCKOFF_PROMPT_TEMPLATE")
    if not prompt_template and os.path.exists("prompt_secret.txt"):
        try:
            with open("prompt_secret.txt", "r", encoding="utf-8") as f:
                prompt_template = f.read()
        except: pass
    if not prompt_template: return None

    csv_data = df.to_csv(index=False)
    latest = df.iloc[-1]
    return prompt_template.replace("{symbol}", symbol).replace("{latest_time}", str(latest["date"])).replace("{latest_price}", str(latest["close"])).replace("{csv_data}", csv_data)

def call_gemini_http(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("GEMINI_API_KEY missing")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    print(f"   >>> Call Gemini (HTTP: {model_name})...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "system_instruction": {"parts": [{"text": "You are Richard D. Wyckoff. You follow strict Wyckoff logic."}]},
        "generationConfig": {"temperature": 0.2}
    }
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200: raise Exception(f"Gemini Error {resp.status_code}: {resp.text}")
    return resp.json()['candidates'][0]['content']['parts'][0]['text']

def call_openai_official(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: raise ValueError("OPENAI_API_KEY missing")
    print(f"   >>> Call OpenAI...")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=os.getenv("AI_MODEL", "gpt-4o"), 
        messages=[{"role": "system", "content": "You are Richard D. Wyckoff."}, {"role": "user", "content": prompt}],
        temperature=0.2 
    )
    return resp.choices[0].message.content

def ai_analyze(symbol, df):
    prompt = get_prompt_content(symbol, df)
    if not prompt: return "Error: No Prompt"
    try: return call_gemini_http(prompt)
    except: 
        print("Switching to OpenAI...")
        try: return call_openai_official(prompt)
        except Exception as e: return f"Analysis Failed: {e}"

# ==========================================
# 4. PDF 生成模块 (修复中文方块乱码)
# ==========================================

def generate_pdf_report(symbol, chart_path, report_text, pdf_path):
    print("正在生成 PDF 研报...")
    
    # 1. 转换 Markdown 为 HTML
    html_content = markdown.markdown(report_text)
    
    # 2. 获取绝对路径
    abs_chart_path = os.path.abspath(chart_path)
    
    # === 关键修复：指定 Ubuntu 下中文字体文件的绝对路径 ===
    # fonts-wqy-microhei 安装后的标准路径通常是下面这个
    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    
    # 为了防止本地运行报错，加个判断 (本地可以用微软雅黑)
    if not os.path.exists(font_path):
        # 如果是本地 Windows/Mac，尝试 fallback (这里只是示例，主要为了服务器不报错)
        font_path = "msyh.ttc" 
    
    # 3. 构建 HTML (使用 @font-face 强制加载字体)
    full_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            /* 核心：定义中文字体 */
            @font-face {{
                font-family: "MyChineseFont";
                src: url("{font_path}");
            }}

            @page {{
                size: A4;
                margin: 1cm;
                @frame footer_frame {{
                    -pdf-frame-content: footerContent;
                    bottom: 0cm;
                    margin-left: 1cm;
                    margin-right: 1cm;
                    height: 1cm;
                }}
            }}
            
            body {{
                /* 应用定义的字体 */
                font-family: "MyChineseFont", sans-serif;
                font-size: 12px;
                line-height: 1.5;
            }}
            
            /* 确保标题和正文都继承字体 */
            h1, h2, h3, p, div {{ 
                font-family: "MyChineseFont", sans-serif; 
                color: #2c3e50;
            }}
            
            img {{ width: 100%; height: auto; margin-bottom: 20px; }}
            .header {{ text-align: center; margin-bottom: 20px; color: #7f8c8d; font-size: 10px; }}
            
            /* 代码块样式优化 */
            pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">Wyckoff Quantitative Analysis Report | Generated by AI Agent</div>
        
        <img src="{abs_chart_path}" />
        
        <hr/>
        
        {html_content}
        
        <div id="footerContent" style="text-align:right; color:#bdc3c7; font-size:8px;">
            Target: {symbol} | Data Source: EastMoney | Font: WenQuanYi Micro Hei
        </div>
    </body>
    </html>
    """
    
    # 4. 生成 PDF
    try:
        with open(pdf_path, "wb") as pdf_file:
            pisa.CreatePDF(full_html, dest=pdf_file)
        print(f"[OK] PDF Generated: {pdf_path}")
    except Exception as e:
        print(f"[Error] PDF 生成失败: {e}")

# ==========================================
# 5. 主程序
# ==========================================

def main():
    symbol = os.getenv("SYMBOL", "600970") 
    df = fetch_a_share_minute(symbol)
    if df.empty: exit(1)
    df = add_indicators(df)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("data", exist_ok=True)
    os.makedirs("reports", exist_ok=True)

    # 保存数据
    csv_path = f"data/{symbol}_1min_{ts}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # 生成图表
    chart_path = f"reports/{symbol}_chart_{ts}.png"
    generate_local_chart(symbol, df, chart_path)

    # AI 分析
    report_text = ai_analyze(symbol, df)
    
    # 保存 Markdown (备份用)
    md_path = f"reports/{symbol}_report_{ts}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # === 生成 PDF (用于推送) ===
    pdf_path = f"reports/{symbol}_report_{ts}.pdf"
    generate_pdf_report(symbol, chart_path, report_text, pdf_path)

if __name__ == "__main__":
    main()

