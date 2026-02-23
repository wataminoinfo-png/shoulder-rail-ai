port os
import sys
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# 環境変数からLINEの鍵を取得（Renderで設定します）
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    # 2025年最新エビデンス（ナラティブレビュー）に基づく簡易診断ロジック
    # ユーザーのキーワードから「病期（フェーズ）」を推定
    if "夜間痛" in user_message or "激痛" in user_message:
        reply_text = (
            "【AI診断：炎症期（フェーズ1）の可能性】\n\n"
            "2025年の最新レビューに基づくと、現在は組織の炎症が強い時期です。\n"
            "無理なストレッチは逆効果になるリスクがあります。\n\n"
            "戦略的アドバイス：\n"
            "・まずは「安静」と「痛みの管理」を優先してください。\n"
            "・夜間のポジショニング（クッション活用）が有効です。\n\n"
            "詳細な回復レールを確認したい方は、個別相談をご活用ください。"
        )
    elif "固まった" in user_message or "上がらない" in user_message:
        reply_text = (
            "【AI診断：凍結期（フェーズ2）の可能性】\n\n"
            "現在は炎症が落ち着き、組織の癒着（固まり）が主体の時期です。\n"
            "Hand誌のデータでは、放置すると4年後も40%に症状が残るリスクがあります。\n\n"
            "戦略的アドバイス：\n"
            "・痛みのない範囲での「愛護的な可動域訓練」を開始する時期です。\n"
            "・無理に動かさず、正しい『回復レール』に乗ることが重要です。"
        )
    else:
        reply_text = (
            "メッセージありがとうございます。\n\n"
            "「夜間痛がある」「肩が上がらない」など、現在の状況を教えていただけますか？\n"
            "2025年最新エビデンスに基づき、あなたの『肩の現在地』を診断します。"
        )

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
