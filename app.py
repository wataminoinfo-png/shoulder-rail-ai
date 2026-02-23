import os
import sys
import glob
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
from PyPDF2 import PdfReader

app = Flask(__name__)

# 環境変数から設定を取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GOOGLE_API_KEY)

def extract_text_from_pdf(pdf_path):
    """PDFファイルからテキストを抽出する"""
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

def get_knowledge_base():
    """knowledgeフォルダ内の全テキストとPDFの内容を結合して取得する"""
    knowledge_text = ""
    knowledge_dir = 'knowledge'
    
    if not os.path.exists(knowledge_dir):
        return "現在、知識ベースに登録されている資料はありません。"
    
    # テキストファイルの読み込み
    for txt_file in glob.glob(os.path.join(knowledge_dir, "*.txt")):
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                knowledge_text += f"\n--- Source: {os.path.basename(txt_file)} ---\n"
                knowledge_text += f.read() + "\n"
        except Exception as e:
            print(f"Error reading txt {txt_file}: {e}")
            
    # PDFファイルの読み込み
    for pdf_file in glob.glob(os.path.join(knowledge_dir, "*.pdf")):
        knowledge_text += f"\n--- Source: {os.path.basename(pdf_file)} ---\n"
        knowledge_text += extract_text_from_pdf(pdf_file) + "\n"
        
    # 知識ベースが空の場合のフォールバック
    if not knowledge_text.strip():
        return "知識ベースに有効なテキストデータが見つかりませんでした。"
        
    return knowledge_text

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
    
    try:
        # 知識ベースの読み込み
        knowledge = get_knowledge_base()
        
        # システムプロンプトの構築
        system_instruction = (
            "あなたは肩関節や理学療法、医学的知識に精通した専門的なアシスタントです。"
            "以下の提供された【知識ベース】を最優先で参照して回答してください。"
            "知識ベースにない内容については、一般的な医学的根拠に基づいて回答しつつ、"
            "「提供された資料には直接的な記載がありませんが、一般的な知見としては〜」と補足してください。"
            "回答はLINEで読みやすいよう、適宜改行を入れ、丁寧かつ簡潔（最大500文字程度）にまとめてください。\n\n"
            f"【知識ベース】\n{knowledge}"
        )
        
        # Gemini 1.5 Flashを使用して回答を生成
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(user_message)
        reply_text = response.text
        
    except Exception as e:
        print(f"Error during Gemini generation: {e}")
        reply_text = f"申し訳ありません。回答の生成中にエラーが発生しました。\nエラー内容: {str(e)[:100]}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
