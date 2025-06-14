import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, PostbackAction,
    QuickReply, QuickReplyButton
)

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler      = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# -------------------- ตารางตัดสินรางวัล --------------------
DECISION = {
    ("A1", "B1", "C1"): "นวัตกรรมการบริการ",
    ("A1", "B3", "C1"): "นวัตกรรมการบริการ",
    ("A1", "B3", "C2"): "ขยายผลมาตรฐานการบริการ",
    ("A1", "B1", "C3"): "บูรณาการข้อมูลในรูปแบบดิจิทัล",
    ("A1", "B3", "C3"): "บูรณาการข้อมูลในรูปแบบดิจิทัล",
    ("A1", "B1", "C4"): "บริการตอบโจทย์ตรงใจ",
    ("A1", "B3", "C4"): "บริการตอบโจทย์ตรงใจ",
    ("A1", "B1", "C5"): "ยกระดับอำนวยความสะดวก",
    ("A1", "B3", "C5"): "ยกระดับอำนวยความสะดวก",
    ("A1", "B3", "C6"): "ขับเคลื่อนเห็นผล",
    ("A2", "B1", "C7"): "สัมฤทธิผล ปชช.มีส่วนร่วม",
    ("A2", "B3", "C7"): "สัมฤทธิผล ปชช.มีส่วนร่วม",
    ("A2", "B3", "C2"): "เลื่องลือขยายผล"
}

# -------------------- helper สร้าง Quick-Reply (วิธี 2) --------------------
def qr(buttons):
    """
    buttons = [(short_label, postback_data, full_display_text), ...]
              short_label ≤ 20 char
    """
    return QuickReply(items=[
        QuickReplyButton(
            action=PostbackAction(
                label=lbl,          # ≤ 20 char
                data=data,          # ค่าใช้ในลอจิก
                display_text=full   # ข้อความยาวที่ผู้ใช้เห็น
            )
        )
        for lbl, data, full in buttons
    ])

# -------------------- state ต่อผู้ใช้ --------------------
user_state = {}           # {uid: {"step":0/1/2, "A":..., "B":..., "C":...}}
def reset(uid):
    user_state[uid] = {"step": 0, "A": None, "B": None, "C": None}

# -------------------- Webhook --------------------
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# -------------------- เมื่อได้รับ “ข้อความ” --------------------
@handler.add(MessageEvent, message=TextMessage)
def on_text(event):
    uid  = event.source.user_id
    text = event.message.text.strip()

    if text.lower() in ("เริ่ม", "เริ่มใหม่", "reset"):
        reset(uid); ask_q1(event.reply_token); return

    if uid not in user_state:
        reset(uid); ask_q1(event.reply_token); return

    # ถ้าไม่ใช่ปุ่มของเรา
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage('โปรดกดปุ่มที่กำหนด หรือพิมพ์ "เริ่ม" เพื่อเริ่มใหม่')
    )

# -------------------- เมื่อได้รับ Postback --------------------
@handler.add(PostbackEvent)
def on_postback(event):
    uid  = event.source.user_id
    data = event.postback.data
    st   = user_state.get(uid) or reset(uid) or user_state[uid]

    # ----- Q1 -----
    if st["step"] == 0 and data.startswith("A"):
        st["A"]   = data
        st["step"] = 1
        if data == "A3":                    # กลุ่ม PMQA จบเลย
            reply_done(event.reply_token, "PMQA")
            reset(uid); return
        ask_q2(event.reply_token); return

    # ----- Q2 -----
    if st["step"] == 1 and data.startswith("B"):
        if data == "B0":                    # < 1 ปี ไม่เข้าเกณฑ์
            reply_done(event.reply_token, "ผลงานต้องดำเนินการไม่น้อยกว่า 1 ปี")
            reset(uid); return
        st["B"]   = data
        st["step"] = 2
        ask_q3(event.reply_token); return

    # ----- Q3 -----
    if st["step"] == 2 and data.startswith("C"):
        st["C"] = data
        result  = DECISION.get(
            (st["A"], st["B"], st["C"]),
            "ยังไม่พบประเภทที่ตรง โปรดปรึกษาเจ้าหน้าที่"
        )
        reply_done(event.reply_token, result)
        reset(uid); return

# -------------------- คำถาม --------------------
def ask_q1(token):
    line_bot_api.reply_message(token, TextSendMessage(
        "Q1: ผลงานหลักด้านใดมากที่สุด?",
        quick_reply=qr([
            ("บริการปชช.",   "A1", "การให้บริการประชาชน"),
            ("เครือข่าย",    "A2", "การมีส่วนร่วมประชาชน / เครือข่าย"),
            ("ยกระดับ PMQA", "A3", "ยกระดับระบบบริหาร-จัดการองค์กร (PMQA)"),
            ("อื่น / ไม่แน่ใจ","A0", "อื่น ๆ / ยังไม่แน่ใจ")
        ])
    ))

def ask_q2(token):
    line_bot_api.reply_message(token, TextSendMessage(
        "Q2: ผลงานนำไปใช้จริงนานเท่าใด?",
        quick_reply=qr([
            ("ยังไม่ถึง 1 ปี", "B0", "ยังไม่ถึง 1 ปี"),
            ("1-3 ปี",        "B1", "1 – 3 ปี"),
            ("3 ปี+",         "B3", "3 ปีขึ้นไป")
        ])
    ))

def ask_q3(token):
    line_bot_api.reply_message(token, TextSendMessage(
        "Q3: จุดเด่นของผลงานตรงข้อใดมากที่สุด?",
        quick_reply=qr([
            ("นวัตกรรม",   "C1", "สร้างนวัตกรรมใหม่ก่อนใคร"),
            ("ขยายผลเดิม", "C2", "ต่อยอด/ขยายผลจากรางวัลเดิม"),
            ("ดิจิทัลหลายหน", "C3", "บูรณาการข้อมูลดิจิทัลหลายหน่วยงาน"),
            ("Pain Point", "C4", "แก้ Pain Point / End-to-End Process"),
            ("เร็ว-ถูก-โปร่ง", "C5", "ลดขั้นตอน เร็วขึ้น ถูกลง โปร่งใส"),
            ("Agenda สูง",  "C6", "Agenda Impact สูงระดับประเทศ"),
            ("ปชช.ร่วมตัด", "C7", "เน้นให้ประชาชนร่วมตัดสินใจจริงจัง")
        ])
    ))

def reply_done(token, msg):
    line_bot_api.reply_message(token, TextSendMessage(
        f"ผลการประเมินเบื้องต้น:\n{msg}"
    ))

# -------------------- run บน Render --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)