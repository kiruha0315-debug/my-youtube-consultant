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
st.title("🛸 YouTube AI 運営司令塔 (エラー回避版)")

# --- 2. API設定 (サイドバー) ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    hf_key = st.text_input("Hugging Face Token", value=st.secrets.get("HF_TOKEN", ""), type="password")
    st.info("※HF_TOKENはHugging FaceのSettingsで作成したものを入力してください。")

# --- 3. 画像生成関数 (エラー回避・リトライ・予備モデル機能付) ---
def generate_image(prompt, token):
    # 第一候補: FLUX (最新) / 第二候補: Stable Diffusion 2.1 (安定)
    models = [
        "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
        "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"
    ]
    headers = {"Authorization": f"Bearer {token}"}
    
    for model_url in models:
        for i in range(2): # 各モデルで2回リトライ
            try:
                response = requests.post(model_url, headers=headers, json={"inputs": prompt}, timeout=30)
                if response.status_code == 200:
                    return response.content
                elif response.status_code == 503:
                    st.warning(f"🎨 モデルを起動中... 20秒お待ちください")
                    time.sleep(20)
                    continue
                else:
                    break # 次のモデルへ
            except:
                continue
    return None

# --- 4. メイン処理 ---
url = st.text_input("分析したいチャンネルURL", placeholder="https://www.youtube.com/@handle")

if st.button("🛰️ 全機能を一括起動"):
    if not yt_key or not gr_key or not hf_key or not url:
        st.error("全てのAPIキーを入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            groq_client = Groq(api_key=gr_key)

            # --- データ取得 ---
            with st.spinner("🔍 チャンネルをスキャン中..."):
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

                # 動画リスト取得
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
                        '高評価率': round((likes/views*100), 2) if views > 0 else 0,
                        '投稿日': v_res['snippet']['publishedAt'][:10]
                    })
                df = pd.DataFrame(video_data)
                v_id = v_ids[0]

            # --- AI分析 ＆ 画像生成 ---
            col_left, col_right = st.columns([2, 1])
            
            with st.spinner("🧠 戦略を立案 ＆ 🎨 画像を生成中..."):
                # Groq分析
                prompt = f"YouTubeプロデューサーとして、以下のデータを分析し、次作の台本とハッシュタグを提案して：\n{df.to_string()}"
                completion = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                report = completion.choices[0].message.content
                
                # 画像生成
                img_prompt = f"A professional YouTube thumbnail about {df['タイトル'].iloc[0]}"
                image_bytes = generate_image(img_prompt, hf_key)

            # --- 結果表示 ---
            st.success(f"✅ {ch_title} の分析完了")
            t1, t2, t3 = st.tabs(["🚀 戦略レポート", "📊 グラフ分析", "🖼️ サムネイル案"])
            
            with t1:
                st.markdown(report)
            with t2:
                fig = px.bar(df, x='再生数', y='タイトル', orientation='h', color='再生数', color_continuous_scale='Turbo')
                st.plotly_chart(fig, use_container_width=True)
            with t3:
                if image_bytes:
                    st.image(Image.open(io.BytesIO(image_bytes)))
                else:
                    st.warning("現在AIモデルが混み合っています。少し待ってから再度実行してください。")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
