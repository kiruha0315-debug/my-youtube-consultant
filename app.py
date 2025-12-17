import streamlit as st
import pandas as pd
import plotly.express as px
from googleapiclient.discovery import build
from groq import Groq
from openai import OpenAI

# 1. ページ設定
st.set_page_config(page_title="YouTube AI Analytics", layout="wide", page_icon="📈")
st.title("📈 YouTube 詳細分析 & AIコンサル")

# 2. API設定 (サイドバー)
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    oa_key = st.text_input("OpenAI API Key (任意)", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

url = st.text_input("分析したいチャンネルURL", placeholder="https://www.youtube.com/@handle")

if st.button("📊 詳細分析を開始"):
    if not yt_key or not gr_key or not url:
        st.error("APIキーとURLを正しく入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            
            # --- 1. チャンネルIDの特定 ---
            with st.spinner("🔍 チャンネルを特定中..."):
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
            else:
                # --- 2. 動画データの取得 ---
                with st.spinner("📊 最新の動画データを取得中..."):
                    ch_res = youtube.channels().list(id=c_id, part='contentDetails').execute()
                    playlist_id = ch_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    pl_res = youtube.playlistItems().list(playlistId=playlist_id, part='snippet', maxResults=10).execute()
                    
                    video_data = []
                    for item in pl_res['items']:
                        v_id = item['snippet']['resourceId']['videoId']
                        v_res = youtube.videos().list(id=v_id, part='snippet,statistics').execute()['items'][0]
                        
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

                # --- 3. グラフ表示 ---
                st.header("📊 パフォーマンス可視化")
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.subheader("動画別再生数")
                    fig = px.bar(df, x='再生数', y='タイトル', orientation='h', 
                                 color='再生数', color_continuous_scale='Reds')
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)

                with col_b:
                    st.subheader("エンゲージメント (再生 vs 高評価率)")
                    fig2 = px.scatter(df, x='再生数', y='高評価率', size='高評価',
                                      hover_name='タイトル', color='高評価率')
                    st.plotly_chart(fig2, use_container_width=True)

                # --- 4. 個別詳細カード ---
                st.header("🔍 動画別詳細レポート")
                for index, row in df.iterrows():
                    with st.expander(f"【{index+1}】 {row['タイトル']}"):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("再生数", f"{row['再生数']:,}回")
                        c2.metric("高評価数", f"{row['高評価']:,}件")
                        c3.metric("高評価率", f"{row['高評価率']}%")
                        if row['再生数'] > df['再生数'].mean():
                            st.success("🌟 平均より伸びています！")
                        else:
                            st.info("💡 さらなる改善の余地があります。")

                # --- 5. AI戦略レポート ---
                with st.spinner("🧠 AIが最強の戦略を立案中..."):
                    groq_client = Groq(api_key=gr_key)
                    prompt = f"以下のYouTubeデータから、ヒット分析、企画案、ショートと通常のダブル台本、SEOタグ、画像プロンプトを作成して：\n{df.to_string()}"
                    
                    completion = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    report = completion.choices[0].message.content
                    st.header("💡 AI戦略レポート")
                    st.markdown(report)

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
