import os
import sys
import glob
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

# 環境変数
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GOOGLE_API_KEY)

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
        return f"(Error reading file: {os.path.basename(pdf_path)})"
    return text

def get_knowledge_base():
    knowledge_text = ""
    knowledge_dir = 'knowledge'
    
    if not os.path.exists(knowledge_dir):
        return "知識ベースフォルダが見つかりません。"
    
    # 全てのファイルを取得（日本語名対策として、globではなくos.listdirを使用）
    files = os.listdir(knowledge_dir)
    logger.info(f"Found files in knowledge: {files}")

    for filename in files:
        file_path = os.path.join(knowledge_dir, filename)
        if filename.lower().endswith('.txt'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    knowledge_text += f"\n--- Source: {filename} ---\n{f.read()}\n"
            except Exception as e:
                logger.error(f"Error reading {filename}: {e}")
        elif filename.lower().endswith('.pdf'):
            knowledge_text += f"\n--- Source: {filename} ---\n{extract_text_from_pdf(file_path)}\n"
            
    if not knowledge_text.strip():
        return "知識ベースに有効なテキストデータがありません。"
    
    # テキストが長すぎる場合の制限（Geminiの入力制限対策）
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
    logger.info(f"Received message: {user_message}")
    
    try:
        knowledge = get_knowledge_base()
        
        system_instruction = (
            "あなたは肩関節や理学療法、医学的知識に精通した専門的なアシスタントです。"
            "以下の提供された【知識ベース】を最優先で参照して回答してください。"
            "知識ベースにない内容については、一般的な医学的根拠に基づいて回答しつつ、"
            "「提供された資料には直接的な記載がありませんが、一般的な知見としては〜」と補足してください。"
            "回答はLINEで読みやすいよう、適宜改行を入れ、丁寧かつ簡潔にまとめてください。\n\n"
            f"【知識ベース】\n{knowledge}"
        )
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(user_message)
        reply_text = response.text
        
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        reply_text = f"申し訳ありません。エラーが発生しました。\n原因: {str(e)[:50]}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
