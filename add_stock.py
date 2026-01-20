import os
import re
import time
import requests
from datetime import datetime
# 引入 Google Sheets 管理模块
from sheet_manager import SheetManager 

def get_telegram_updates(bot_token):
    """获取 Telegram 机器人最近收到的消息"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        # timeout=10 避免卡死
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception as e:
        print(f"获取消息失败: {e}")
    return []

def send_reply(bot_token, chat_id, text):
    """发送回复消息"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

def main():
    bot_token = os.getenv("TG_BOT_TOKEN")
    admin_chat_id = os.getenv("TG_CHAT_ID")

    if not bot_token:
        print("❌ 错误：未设置 TG_BOT_TOKEN")
        return

    # 1. 尝试连接 Google Sheets
    print("☁️ 正在连接 Google Sheets...")
    try:
        sm = SheetManager()
        print("✅ 表格连接成功")
    except Exception as e:
        print(f"❌ 表格连接失败: {e}")
        return

    # 2. 获取消息
    updates = get_telegram_updates(bot_token)
    if not updates:
        print("📭 没有新消息")
        return

    print(f"📥 收到 {len(updates)} 条消息，开始处理...")

    latest_update_id = 0
    current_time = time.time()
    
    for update in updates:
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()
        date = message.get("date", 0)
        update_id = update.get("update_id")

        latest_update_id = max(latest_update_id, update_id)

        # 安全检查
        if admin_chat_id and chat_id != str(admin_chat_id):
            continue

        # 时间检查 (只处理最近 40 分钟的消息)
        if current_time - date > 2400: 
            continue

        print(f"  -- 处理消息: {text}")

        # ==================== 指令处理逻辑 ====================

        # 1. 【清空】指令
        if re.search(r"(清空|clear)", text, re.IGNORECASE):
            sm.clear_all()
            send_reply(bot_token, chat_id, "🗑 <b>表格已清空。</b>")
            continue

        # 2. 【查看】指令
        if re.search(r"(查看|查询|列表|list|ls|cx)", text, re.IGNORECASE):
            stocks = sm.get_all_stocks()
            if stocks:
                msg_lines = [f"📋 <b>当前云端持仓 ({len(stocks)}只):</b>"]
                for code, info in stocks.items():
                    # 只有当数量或价格不为0时，才显示详细信息，否则只显示代码
                    if str(info['qty']) != "0" or str(info['price']) != "0.0":
                        detail = f" | 📅{info['date']} | 📦{info['qty']} | 💰{info['price']}"
                        msg_lines.append(f"• <code>{code}</code>{detail}")
                    else:
                        msg_lines.append(f"• <code>{code}</code>")
                send_reply(bot_token, chat_id, "\n".join(msg_lines))
            else:
                send_reply(bot_token, chat_id, "📭 <b>当前表格为空。</b>")
            continue

        # 3. 【删除】指令
        if re.search(r"(删除|移除|del|rm)", text, re.IGNORECASE):
            codes_to_del = re.findall(r"\d{6}", text)
            deleted_list = []
            for code in codes_to_del:
                if sm.remove_stock(code):
                    deleted_list.append(code)
            
            if deleted_list:
                send_reply(bot_token, chat_id, f"➖ <b>已从表格移除:</b>\n{', '.join(deleted_list)}")
            else:
                send_reply(bot_token, chat_id, "⚠️ 未找到要删除的股票代码")
            continue

        # 4. 【添加/更新】指令 (默认)
        # 逻辑：如果没有触发上面的指令，且包含数字，就尝试添加
        
        # A. 尝试匹配详细格式: "600519 2025-01-01 100 15.5"
        # 正则含义: 6位代码 + 空格 + 日期 + 空格 + 数量 + 空格 + 价格
        match_detail = re.search(r"(\d{6})\s+(\d{4}-\d{2}-\d{2})\s+(\d+)\s+(\d+(?:\.\d+)?)", text)
        
        if match_detail:
            c, d, q, p = match_detail.groups()
            res = sm.add_or_update_stock(c, d, q, p)
            status = "新增" if res == "Added" else "更新"
            send_reply(bot_token, chat_id, f"✅ <b>已{status}持仓:</b>\nCode: {c}\nCost: {p}\nQty: {q}\nDate: {d}")
        
        else:
            # B. 简易模式: 只提取所有6位代码
            codes = re.findall(r"\d{6}", text)
            added_codes = []
            for code in codes:
                # 只有当代码不存在时才添加默认值，防止覆盖已有的详细数据
                # add_or_update_stock 内部逻辑：如果已存在且参数为空，不会覆盖旧数据
                # 这里我们需要稍微判断一下，为了简单起见，我们调用 sm 的方法
                # 如果 sm.add_or_update_stock 仅传 code，它会检查是否存在
                res = sm.add_or_update_stock(code) 
                if res == "Added":
                    added_codes.append(code)
                elif res == "Updated":
                    # 如果只是更新了默认值，其实不需要提示，或者提示已存在
                    pass
            
            if added_codes:
                send_reply(bot_token, chat_id, f"➕ <b>已加入监控:</b>\n{', '.join(added_codes)}")

    # 3. 消费消息 (防止下次重复处理)
    if latest_update_id > 0:
        try:
            requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={latest_update_id + 1}", timeout=5)
        except:
            pass

if __name__ == "__main__":
    main()
