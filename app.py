import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build
from groq import Groq
import requests
import io
from PIL import Image

# 1. ページ設定
st.set_page_config(page_title="YouTube AI Command Center Free", layout="wide", page_icon="🛸")
st.title("🛸 YouTube AI 運営司令塔（HuggingFace無料版）")

# 2. API設定
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    hf_key = st.text_input("Hugging Face Token", value=st.secrets.get("HF_TOKEN", ""), type="password")
    st.info("Hugging Face Token は無料で作れます。画像生成に使用します。")

# --- 画像生成関数 (Hugging Face APIを使用) ---
def generate_image(prompt, token):
    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
    return response.content

url = st.text_input("分析したいチャンネルURL")

if st.button("🛰️ 無料AIフルパワー起動"):
    if not yt_key or not gr_key or not hf_key or not url:
        st.error("全てのAPIキーを入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            groq_client = Groq(api_key=gr_key)

            # (中略: チャンネル特定・データ取得のロジックをここに配置)
            # 変数 df と最新の v_id がある前提

            # --- 1. コメント分析 (Groq: 無料) ---
            with st.spinner("💬 視聴者の本音を分析中..."):
                comment_res = youtube.commentThreads().list(videoId=v_id, part='snippet', maxResults=30).execute()
                all_comments = "\n".join([item['snippet']['topLevelComment']['snippet']['textDisplay'] for item in comment_res['items']])
                sent_res = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"コメント分析して：{all_comments}"}]
                )
                sentiment_report = sent_res.choices[0].message.content

            # --- 2. 画像生成 (Hugging Face: 無料) ---
            with st.spinner("🎨 サムネイル画像を生成中..."):
                img_prompt = f"Professional YouTube thumbnail for a video about {df['タイトル'].iloc[0]}, high quality, vivid colors"
                image_bytes = generate_image(img_prompt, hf_key)
                image = Image.open(io.BytesIO(image_bytes))

            # --- 3. 結果表示 ---
            st.success("✅ 全て完了！")
            tab1, tab2, tab3 = st.tabs(["🚀 戦略・台本", "📊 分析グラフ", "🖼️ サムネイル案"])
            
            with tab1:
                # Groqによる戦略レポートを表示
                st.markdown(sentiment_report)
            
            with tab2:
                # Plotlyグラフを表示
                fig = px.bar(df, x='再生数', y='タイトル', orientation='h')
                st.plotly_chart(fig)

            with tab3:
                st.image(image, caption="AI生成サムネイル（無料版）")

        except Exception as e:
            st.error(f"エラー: {e}")
