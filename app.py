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
st.set_page_config(page_title="YouTube AI Consultant PRO", layout="wide", page_icon="📈")
st.title("📈 YouTube AI 運営司令塔 (徹底分析・改善版)")

# --- 2. API設定 ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    hf_key = st.text_input("Hugging Face Token", value=st.secrets.get("HF_TOKEN", ""), type="password")

# --- 3. 関数定義 ---
def generate_image(prompt, token):
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {token}"}
    for i in range(2):
        try:
            response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=40)
            if response.status_code == 200: return response.content
            elif response.status_code == 503: time.sleep(20); continue
        except: continue
    return None

def get_channel_data(youtube, url, label="対象"):
    try:
        c_id = None
        if "/channel/" in url: 
            c_id = url.split("/channel/")[1].split("?")[0].split("/")[0]
        elif "/@" in url:
            handle = url.split("/@")[1].split("?")[0].split("/")[0]
            res = youtube.search().list(q=f"@{handle}", type="channel", part="snippet", maxResults=1).execute()
            if res.get('items'): c_id = res['items'][0]['snippet']['channelId']
        
        if not c_id: return None, None, None, None
        
        ch_res = youtube.channels().list(id=c_id, part='snippet,contentDetails').execute()['items'][0]
        title = ch_res['snippet']['title']
        uploads_id = ch_res['contentDetails']['relatedPlaylists']['uploads']
        
        pl_res = youtube.playlistItems().list(playlistId=uploads_id, part='snippet', maxResults=5).execute()
        v_data = []
        for item in pl_res.get('items', []):
            vid = item['snippet']['resourceId']['videoId']
            v_res = youtube.videos().list(id=vid, part='snippet,statistics').execute()['items'][0]
            views = int(v_res['statistics'].get('viewCount', 0))
            likes = int(v_res['statistics'].get('likeCount', 0))
            v_data.append({
                'チャンネル': title,
                '区分': label,
                'タイトル': v_res['snippet']['title'],
                '再生数': views,
                '高評価率': round((likes/views*100), 2) if views > 0 else 0,
                'コメント数': int(v_res['statistics'].get('commentCount', 0)),
                '投稿日': v_res['snippet']['publishedAt'][:10],
                'v_id': vid
            })
        return title, pd.DataFrame(v_data), v_data[0]['v_id'] if v_data else None, c_id
    except: return None, None, None, None

# --- 4. メイン入力エリア ---
col_in1, col_in2 = st.columns(2)
with col_in1:
    my_url = st.text_input("自分のチャンネルURL", placeholder="https://www.youtube.com/@my_ch")
with col_in2:
    rival_url = st.text_input("競合のチャンネルURL (空欄なら自動検索)", placeholder="https://www.youtube.com/@rival_ch")

if st.button("🚀 チャンネル徹底診断 ＆ 台本生成"):
    if not yt_key or not gr_key or not hf_key or not my_url:
        st.error("APIキーと自分のURLは必須です。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            groq_client = Groq(api_key=gr_key)

            # --- STEP 1: データ収集 ---
            with st.spinner("📊 チャンネルデータをスキャン中..."):
                my_name, my_df, my_vid, my_c_id_val = get_channel_data(youtube, my_url, "自分")
                
                if my_df is None or my_df.empty:
                    st.error("自分のチャンネルデータが取得できませんでした。URLを確認してください。")
                    st.stop()

                rival_dfs = [my_df]
                # 競合データの取得 (手動入力優先)
                if rival_url:
                    _, r_df, _, _ = get_channel_data(youtube, rival_url, "指定競合")
                    if r_df is not None: rival_dfs.append(r_df)
                else:
                    # 自動検索
                    search_q = my_df['タイトル'].iloc[0][:15]
                    s_res = youtube.search().list(q=search_q, type="video", part="snippet", maxResults=3).execute()
                    found_ids = {my_c_id_val}
                    for item in s_res.get('items', []):
                        rc_id = item['snippet']['channelId']
                        if rc_id not in found_ids:
                            _, rdf, _, _ = get_channel_data(youtube, f"https://www.youtube.com/channel/{rc_id}", "自動競合")
                            if rdf is not None: 
                                rival_dfs.append(rdf)
                                found_ids.add(rc_id)
                
                all_df = pd.concat(rival_dfs, ignore_index=True)

            # --- STEP 2: コメント取得 ---
            try:
                c_res = youtube.commentThreads().list(videoId=my_vid, part='snippet', maxResults=20).execute()
                comments = "\n".join([i['snippet']['topLevelComment']['snippet']['textDisplay'] for i in c_res['items']])
            except: comments = "コメント取得不可"

            # --- STEP 3: AIコンサルタントによる分析 ---
            with st.spinner("🧠 AIプロデューサーが分析レポートを作成中..."):
                prompt = f"""
                あなたはYouTube専門の戦略コンサルタントです。以下のデータから【診断】と【処方箋】を出してください。

                【データ】
                自社直近5本: {my_df.to_string()}
                競合比較データ: {all_df.to_string()}
                最新動画の視聴者コメント: {comments}

                --- 以下の構成で回答してください ---
                1. **チャンネル全体診断**: 今のチャンネルの立ち位置と、再生数が伸び悩んでいる（または伸びている）根本原因。
                2. **動画別・個別ダメ出し**: 
                   自社の直近5本の動画タイトルを一つずつ挙げ、データ（再生数・高評価率）に基づいた具体的な「改善点」を辛口で指摘してください。
                3. **競合との徹底比較**: ライバルと比較して、どの要素（企画力、サムネ、投稿頻度など）で負けているか。
                4. **次回作の完全台本（超具体版）**: 
                   - コンセプト: 誰に、どんな価値を届けるか
                   - 冒頭5秒のナレーション: そのまま読める強烈なフック
                   - 本編構成: 飽きさせないための具体的なナレーション原稿
                   - 演出指示: どこでテロップを出し、どこでBGMを盛り上げるか
                5. **サムネイル用パワーワード5選**
                """
                report = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

            # --- STEP 4: 画像生成 ---
            with st.spinner("🎨 サムネイル案を生成中..."):
                image_bytes = generate_image(f"Highly clickable YouTube thumbnail about {my_df['タイトル'].iloc[0]}", hf_key)

            # --- STEP 5: 表示 ---
            st.success("✅ 徹底診断レポートが完成しました！")
            t1, t2, t3 = st.tabs(["💎 徹底診断 ＆ 次回台本", "📊 競合・数字分析", "🖼️ サムネ案"])
            
            with t1:
                st.markdown(report)
            with t2:
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.plotly_chart(px.bar(all_df, x='再生数', y='タイトル', color='区分', orientation='h', title="再生数比較"), use_container_width=True)
                with col_g2:
                    st.plotly_chart(px.scatter(all_df, x='再生数', y='高評価率', color='区分', size='コメント数', hover_name='タイトル', title="満足度分布"), use_container_width=True)
                st.write("### 自社データの詳細")
                st.dataframe(my_df)
            with t3:
                if image_bytes: st.image(Image.open(io.BytesIO(image_bytes)), caption="AI提案サムネイル（背景案）")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
