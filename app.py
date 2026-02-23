import os
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from PyPDF2 import PdfReader

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 環境変数から設定を取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
# APIキーの取得（前後の空白を徹底的に削除）
raw_api_key = os.getenv('GOOGLE_API_KEY')
GOOGLE_API_KEY = raw_api_key.strip() if raw_api_key else None

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"[Page {i+1}]\n{page_text}\n"
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
        return ""
    return text

def get_knowledge_base():
    knowledge_text = ""
    knowledge_dir = 'knowledge'
    if not os.path.exists(knowledge_dir):
        return ""
    try:
        files = os.listdir(knowledge_dir)
        for filename in files:
            file_path = os.path.join(knowledge_dir, filename)
            if filename.lower().endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    knowledge_text += f"\n--- Source: {filename} ---\n{f.read()}\n"
            elif filename.lower().endswith('.pdf'):
                knowledge_text += f"\n--- Source: {filename} ---\n{extract_text_from_pdf(file_path)}\n"
    except Exception as e:
        logger.error(f"Error: {e}")
    return knowledge_text[:30000]

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    
    # APIキーの存在チェック
    if not GOOGLE_API_KEY:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="エラー: GOOGLE_API_KEYが設定されていません。"))
        return

    try:
        # 毎回設定を初期化（キャッシュ対策）
        genai.configure(api_key=GOOGLE_API_KEY)
        knowledge = get_knowledge_base()
        
        prompt = (
            "あなたは肩関節や理学療法の専門家です。提供された【知識ベース】を最優先で参照して回答してください。"
            f"\n\n【知識ベース】\n{knowledge}\n\n"
            f"ユーザーの質問: {user_message}"
        )
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        reply_text = response.text
        
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        # エラーの詳細を表示
        reply_text = f"AI呼び出しエラーが発生しました。\n詳細: {str(e)[:150]}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
