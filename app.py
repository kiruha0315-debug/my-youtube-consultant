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

# --- 3. 関数定義 (画像生成・データ取得) ---
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
        if "/channel/" in url: c_id = url.split("/channel/")[1].split("?")[0].split("/")[0]
        elif "/@" in url:
            handle = url.split("/@")[1].split("?")[0].split("/")[0]
            res = youtube.search().list(q=f"@{handle}", type="channel", part="snippet", maxResults=1).execute()
            if res.get('items'): c_id = res['items'][0]['snippet']['channelId']
        
        if not c_id: return None, None, None
        
        ch_res = youtube.channels().list(id=c_id, part='snippet,contentDetails').execute()['items'][0]
        title = ch_res['snippet']['title']
        uploads_id = ch_res['contentDetails']['relatedPlaylists']['uploads']
        
        pl_res = youtube.playlistItems().list(playlistId=uploads_id, part='snippet', maxResults=5).execute()
        v_data = []
        for item in pl_res.get('items', []):
            vid = item['snippet']['resourceId']['videoId']
            v_res = youtube.videos().list(id=vid, part='snippet,statistics').execute()['items'][0]
            v_data.append({
                'チャンネル': title,
                '区分': label,
                'タイトル': v_res['snippet']['title'],
                '再生数': int(v_res['statistics'].get('viewCount', 0)),
                '高評価率': round((int(v_res['statistics'].get('likeCount', 0))/int(v_res['statistics'].get('viewCount', 1))*100), 2),
                'コメント数': int(v_res['statistics'].get('commentCount', 0)),
                '投稿日': v_res['snippet']['publishedAt'][:10],
                'v_id': vid
            })
        return title, pd.DataFrame(v_data), v_data[0]['v_id']
    except: return None, None, None

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
                my_name, my_df, my_vid = get_channel_data(youtube, my_url, "自分")
                if not my_c_id: # (get_channel_data内で判別済み)
                    pass 

                # 競合データの取得 (手動入力優先)
                rival_dfs = [my_df]
                if rival_url:
                    r_name, r_df, _ = get_channel_data(youtube, rival_url, "指定競合")
                    if r_df is not None: rival_dfs.append(r_df)
                else:
                    # 自動検索
                    q = my_df['タイトル'].iloc[0][:15]
                    s_res = youtube.search().list(q=q, type="video", part="snippet", maxResults=3).execute()
                    for item in s_res.get('items', []):
                        rc_id = item['snippet']['channelId']
                        _, rdf, _ = get_channel_data(youtube, f"https://www.youtube.com/channel/{rc_id}", "自動競合")
                        if rdf is not None: rival_dfs.append(rdf)
                
                all_df = pd.concat(rival_dfs, ignore_index=True)

            # --- STEP 2: コメント取得 ---
            try:
                c_res = youtube.commentThreads().list(videoId=my_vid, part='snippet', maxResults=20).execute()
                comments = "\n".join([i['snippet']['topLevelComment']['snippet']['textDisplay'] for i in c_res['items']])
            except: comments = "コメント取得不可"

            # --- STEP 3: AIコンサルタントによる分析 (プロンプト大幅強化) ---
            with st.spinner("🧠 AIプロデューサーが分析レポートを作成中..."):
                prompt = f"""
                あなたはYouTube専門の戦略コンサルタントです。以下のデータから【診断】と【処方箋】を出してください。

                【データ】
                自社データ: {my_df.to_string()}
                競合比較: {all_df.to_string()}
                最新動画のコメント: {comments}

                --- 以下の構成で回答してください ---
                1. **チャンネル全体診断**: 強み、弱み、改善すべき急務。
                2. **動画別・辛口改善点**: 各動画のタイトルと数字を見て、具体的にどこが悪いか（サムネの引き、テーマの弱さなど）を1本ずつ指摘。
                3. **競合との比較**: 競合に勝っている点、完全に負けている点。
                4. **次回作の神台本**: 
                   - コンセプト・ターゲット
                   - 冒頭5秒の強烈なフックとナレーション
                   - 本編の具体的スクリプト（そのまま読める言葉で）
                   - 演出指示（テロップ、BGMの切り替え）
                5. **サムネイル用パワーワード5選**
                """
                report = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

            # --- STEP 4: 画像生成 ---
            with st.spinner("🎨 サムネイル案を生成中..."):
                image_bytes = generate_image(f"Eye-catching professional YouTube thumbnail: {my_df['タイトル'].iloc[0]}", hf_key)

            # --- STEP 5: 表示 ---
            st.success("✅ 診断と改善案がまとまりました！")
            t1, t2, t3 = st.tabs(["💎 徹底診断 ＆ 次回台本", "📊 競合・数字分析", "🖼️ サムネ・ビジュアル案"])
            
            with t1:
                st.markdown(report)
            with t2:
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.plotly_chart(px.bar(all_df, x='再生数', y='タイトル', color='区分', orientation='h', title="再生数比較"), use_container_width=True)
                with col_g2:
                    st.plotly_chart(px.scatter(all_df, x='再生数', y='高評価率', color='区分', size='コメント数', hover_name='タイトル', title="エンゲージメント分布"), use_container_width=True)
                st.dataframe(my_df)
            with t3:
                if image_bytes: st.image(Image.open(io.BytesIO(image_bytes)))

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
