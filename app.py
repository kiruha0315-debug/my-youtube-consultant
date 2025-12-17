import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build
from groq import Groq
from openai import OpenAI

# 1. ページ設定
st.set_page_config(page_title="YouTube AI Command Center", layout="wide", page_icon="🛸")
st.title("🛸 YouTube AI 運営司令塔（オールインワン）")

# 2. API設定
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    oa_key = st.text_input("OpenAI API Key", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

url = st.text_input("チャンネルURLを入力")

if st.button("🛰️ 全機能を一括起動"):
    if not yt_key or not gr_key or not oa_key or not url:
        st.error("全てのAPIキー（OpenAI含む）とURLを入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            oa_client = OpenAI(api_key=oa_key)
            groq_client = Groq(api_key=gr_key)

            # --- 1. チャンネル特定 ＆ データ取得 ---
            with st.spinner("📊 チャンネルデータを解析中..."):
                # (以前のロジックでチャンネルID特定)
                # 仮に c_id, df, v_id (最新動画ID) が取得できている前提
                # ※動画取得時に最新の v_id を保持してください
                pass 

            # --- 2. 【新機能】コメント感情分析 ---
            with st.spinner("💬 視聴者の本音（コメント）を分析中..."):
                comment_res = youtube.commentThreads().list(
                    videoId=v_id, part='snippet', maxResults=50).execute()
                comments = [item['snippet']['topLevelComment']['snippet']['textDisplay'] for item in comment_res['items']]
                all_comments_text = "\n".join(comments)
                
                # AIによる感情分析
                sentiment_prompt = f"以下のYouTubeコメントを分析し、ポジティブ・ネガティブの割合と、改善点を抽出して：\n{all_comments_text}"
                sent_completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": sentiment_prompt}]
                )
                sentiment_report = sent_completion.choices[0].message.content

            # --- 3. 【新機能】トレンド予測 ---
            with st.spinner("🔥 トレンドを予測中..."):
                trend_prompt = f"「{df['タイトル'].iloc[0]}」のジャンルで、現在世界的にバズり始めている最新キーワードと企画案を3つ出して。"
                trend_res = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": trend_prompt}]
                )
                trend_report = trend_res.choices[0].message.content

            # --- 4. 画像生成 ＆ 【新機能】サムネイル評価 ---
            with st.spinner("🎨 サムネイル生成 ＆ 評価中..."):
                # 画像生成 (DALL-E 3)
                img_response = oa_client.images.generate(
                    model="dall-e-3",
                    prompt=f"A catchy YouTube thumbnail design for: {df['タイトル'].iloc[0]}",
                    size="1024x1024"
                )
                img_url = img_response.data[0].url
                
                # OpenAI (GPT-4o) を使った画像評価
                vision_res = oa_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": "このサムネイルはYouTubeでクリックされますか？0-100点で採点し、視線誘導の観点から改善点を教えて。"},
                            {"type": "image_url", "image_url": {"url": img_url}}
                        ]}
                    ]
                )
                vision_report = vision_res.choices[0].message.content

            # --- 5. 結果表示 (タブで整理) ---
            tab1, tab2, tab3, tab4 = st.tabs(["🎯 戦略・台本", "📈 分析グラフ", "💬 視聴者の声", "🖼️ サムネイル診断"])
            
            with tab1:
                st.subheader("🔥 トレンド予測企画")
                st.markdown(trend_report)
                # (ここに以前の台本なども表示)
            
            with tab2:
                # (以前の Plotly グラフを表示)
                pass

            with tab3:
                st.subheader("😊 視聴者の反応分析")
                st.markdown(sentiment_report)

            with tab4:
                col_i, col_r = st.columns(2)
                with col_i:
                    st.image(img_url, caption="生成されたサムネイル")
                with col_r:
                    st.subheader("🧐 AI診断結果")
                    st.markdown(vision_report)

        except Exception as e:
            st.error(f"エラー: {e}")
