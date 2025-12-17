import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build
from groq import Groq
import requests
import io
import time
from PIL import Image

# --- 1. ページ設定 ---
st.set_page_config(page_title="YouTube AI Command Center", layout="wide", page_icon="🛸")
st.title("🛸 YouTube AI 運営司令塔 (FLUXモデル版)")

# --- 2. API設定 (サイドバー) ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    hf_key = st.text_input("Hugging Face Token", value=st.secrets.get("HF_TOKEN", ""), type="password")
    st.info("※APIキーはStreamlitのSecretsに保存しておくと便利です。")

# --- 3. 画像生成関数 (FLUX.1-schnell モデル) ---
def generate_image(prompt, token):
    # 最新の高速モデル FLUX.1-schnell を使用
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {token}"}
    
    for i in range(3):
        try:
            response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
            
            if response.status_code == 200:
                return response.content
            elif response.status_code == 503 or response.status_code == 429:
                # 読み込み中(503)やリクエスト過多(429)の場合は20秒待機
                st.warning(f"🎨 AI画像生成モデルを準備中... ({i+1}/3回目: 20秒待機)")
                time.sleep(20)
                continue
            else:
                st.error(f"画像生成エラー (Status: {response.status_code})")
                return None
        except Exception as e:
            st.error(f"通信エラー: {e}")
            return None
    return None

# --- 4. メインエリア ---
url = st.text_input("分析したいチャンネルURL", placeholder="https://www.youtube.com/@handle")

if st.button("🛰️ 全機能を一括起動"):
    if not yt_key or not gr_key or not hf_key or not url:
        st.error("全てのAPIキーを入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            groq_client = Groq(api_key=gr_key)

            # --- 1. チャンネル特定 & データ取得 ---
            with st.spinner("🔍 チャンネルデータを解析中..."):
                c_id = None
                if "/channel/" in url:
                    c_id = url.split("/channel/")[1].split("?")[0].split("/")[0]
                elif "/@" in url:
                    handle = url.split("/@")[1].split("?")[0].split("/")[0]
                    res = youtube.search().list(q=f"@{handle}", type="channel", part="snippet", maxResults=1).execute()
                    if res.get('items'):
                        c_id = res['items'][0]['snippet']['channelId']
                
                if not c_id:
                    st.error("チャンネルが見つかりませんでした。")
                    st.stop()

                ch_res = youtube.channels().list(id=c_id, part='snippet,contentDetails').execute()
                ch_title = ch_res['items'][0]['snippet']['title']
                playlist_id = ch_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                pl_res = youtube.playlistItems().list(playlistId=playlist_id, part='snippet', maxResults=10).execute()
                
                video_data = []
                v_ids = []
                for item in pl_res['items']:
                    vid = item['snippet']['resourceId']['videoId']
                    v_ids.append(vid)
                    v_res = youtube.videos().list(id=vid, part='snippet,statistics').execute()['items'][0]
                    
                    views = int(v_res['statistics'].get('viewCount', 0))
                    likes = int(v_res['statistics'].get('likeCount', 0))
                    video_data.append({
                        'タイトル': v_res['snippet']['title'],
                        '再生数': views,
                        '高評価': likes,
                        '高評価率': round((likes / views * 100), 2) if views > 0 else 0,
                        '投稿日': v_res['snippet']['publishedAt'][:10]
                    })
                df = pd.DataFrame(video_data)
                v_id = v_ids[0]

            # --- 2. 競合・コメント・分析 ---
            with st.spinner("🧠 戦略を分析中..."):
                # コメント取得
                try:
                    c_res = youtube.commentThreads().list(videoId=v_id, part='snippet', maxResults=20).execute()
                    all_comments = "\n".join([i['snippet']['topLevelComment']['snippet']['textDisplay'] for i in c_res['items']])
                except:
                    all_comments = "コメント取得不可"

                # Groqによる分析
                prompt = f"YouTube分析と戦略提案をして：\nデータ：{df.to_string()}\nコメント：{all_comments}"
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                report = completion.choices[0].message.content

            # --- 3. 画像生成 ---
            with st.spinner("🎨 サムネイルを生成中..."):
                img_prompt = f"High-quality YouTube thumbnail for: {df['タイトル'].iloc[0]}"
                image_bytes = generate_image(img_prompt, hf_key)

            # --- 4. 結果表示 ---
            st.success(f"✅ {ch_title} の分析完了")
            t1, t2, t3 = st.tabs(["🚀 戦略レポート", "📊 グラフ", "🖼️ サムネイル案"])
            
            with t1:
                st.markdown(report)
            with t2:
                fig = px.bar(df, x='再生数', y='タイトル', orientation='h', color='再生数')
                st.plotly_chart(fig, use_container_width=True)
            with t3:
                if image_bytes:
                    st.image(Image.open(io.BytesIO(image_bytes)))
                else:
                    st.warning("画像生成に失敗しました。時間をおいて再試行してください。")

        except Exception as e:
            st.error(f"エラー: {e}")
