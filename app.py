import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build
from groq import Groq
import requests
import io
from PIL import Image

# --- 1. ページ設定 ---
st.set_page_config(page_title="YouTube AI Command Center", layout="wide", page_icon="🛸")
st.title("🛸 YouTube AI 運営司令塔 (完全無料版)")

# --- 2. API設定 (サイドバー) ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    hf_key = st.text_input("Hugging Face Token", value=st.secrets.get("HF_TOKEN", ""), type="password")
    st.info("※APIキーはStreamlitのSecretsに保存しておくと便利です。")

# --- 画像生成関数 (Hugging Face API) ---
def generate_image(prompt, token):
    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        return response.content
    except:
        return None

# --- メイン入力エリア ---
url = st.text_input("分析したいチャンネルURL", placeholder="https://www.youtube.com/@handle")

if st.button("🛰️ 全機能を一括起動"):
    if not yt_key or not gr_key or not hf_key or not url:
        st.error("全てのAPIキー（YouTube, Groq, HuggingFace）とURLを入力してください。")
    else:
        try:
            # 各クライアント初期化
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

                # 最新動画データの取得
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
                v_id = v_ids[0] # 最新動画ID

            # --- 2. 競合リサーチ ---
            with st.spinner("🛰️ 競合をスパイ中..."):
                keyword = df['タイトル'].iloc[0][:15]
                search_res = youtube.search().list(q=keyword, type="channel", part="snippet", maxResults=2).execute()
                comp_info = [f"{item['snippet']['title']}" for item in search_res.get('items', [])]

            # --- 3. コメント分析 (Groq) ---
            with st.spinner("💬 視聴者の本音を分析中..."):
                try:
                    c_res = youtube.commentThreads().list(videoId=v_id, part='snippet', maxResults=20).execute()
                    all_comments = "\n".join([i['snippet']['topLevelComment']['snippet']['textDisplay'] for i in c_res['items']])
                except:
                    all_comments = "コメントが無効か、取得できませんでした。"

            # --- 4. サムネイル生成 (Hugging Face) ---
            with st.spinner("🎨 AIサムネイル案を生成中..."):
                img_prompt = f"Professional YouTube thumbnail, eye-catching, high resolution, about {df['タイトル'].iloc[0]}"
                image_bytes = generate_image(img_prompt, hf_key)

            # --- 5. AI戦略レポート生成 (Groq) ---
            with st.spinner("🧠 AIプロデューサーが執筆中..."):
                prompt = f"""
                あなたはYouTubeプロデューサーです。
                【自社データ】\n{df.to_string()}\n
                【競合】\n{", ".join(comp_info)}\n
                【視聴者コメント】\n{all_comments}

                依頼：
                1. 競合比較とヒット分析
                2. 次作の「ショート」と「長尺」のダブル台本
                3. SEOタグ・ハッシュタグ
                4. トレンド予測キーワード
                """
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                report = completion.choices[0].message.content

            # --- 6. 結果表示 ---
            st.success(f"✅ {ch_title} の分析が完了しました！")
            
            t1, t2, t3, t4 = st.tabs(["🚀 戦略・台本", "📊 グラフ分析", "🖼️ サムネイル案", "🔍 詳細データ"])
            
            with t1:
                st.markdown(report)
            
            with t2:
                col_a, col_b = st.columns(2)
                with col_a:
                    fig = px.bar(df, x='再生数', y='タイトル', orientation='h', color='再生数', color_continuous_scale='Reds')
                    st.plotly_chart(fig, use_container_width=True)
                with col_b:
                    fig2 = px.scatter(df, x='再生数', y='高評価率', size='高評価', hover_name='タイトル')
                    st.plotly_chart(fig2, use_container_width=True)
            
            with t3:
                if image_bytes:
                    st.image(Image.open(io.BytesIO(image_bytes)), caption="AI生成サムネイル案")
                else:
                    st.warning("画像の生成に失敗しました。トークンを確認するか時間を置いて試してください。")

            with t4:
                st.dataframe(df)

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
