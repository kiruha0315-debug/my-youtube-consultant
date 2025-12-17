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
st.set_page_config(page_title="YouTube AI Writer PRO", layout="wide", page_icon="📝")
st.title("🛰️ YouTube AI 運営司令塔 (構成作家・自動リサーチ版)")

# --- 2. API設定 (サイドバー) ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    hf_key = st.text_input("Hugging Face Token", value=st.secrets.get("HF_TOKEN", ""), type="password")

# --- 3. 画像生成関数 (FLUXモデル) ---
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

# --- 4. チャンネルデータ取得関数 ---
def get_channel_data(youtube, c_id, label="対象"):
    try:
        ch_res = youtube.channels().list(id=c_id, part='snippet,contentDetails').execute()
        if not ch_res.get('items'): return None, None, None
        
        channel = ch_res['items'][0]
        title = channel['snippet']['title']
        uploads_id = channel['contentDetails']['relatedPlaylists']['uploads']
        
        pl_res = youtube.playlistItems().list(playlistId=uploads_id, part='snippet', maxResults=5).execute()
        v_data = []
        v_ids = []
        
        for item in pl_res.get('items', []):
            vid = item['snippet']['resourceId']['videoId']
            v_ids.append(vid)
            v_res = youtube.videos().list(id=vid, part='snippet,statistics').execute()['items'][0]
            views = int(v_res['statistics'].get('viewCount', 0))
            likes = int(v_res['statistics'].get('likeCount', 0))
            v_data.append({
                'チャンネル': title,
                '区分': label,
                'タイトル': v_res['snippet']['title'],
                '再生数': views,
                '高評価率': round((likes/views*100), 2) if views > 0 else 0,
                'v_id': vid
            })
        return title, pd.DataFrame(v_data), v_ids[0]
    except: return None, None, None

# --- 5. メイン入力エリア ---
my_url = st.text_input("あなたのチャンネルURLを入力", placeholder="https://www.youtube.com/@handle")

if st.button("🛰️ 自動リサーチ ＆ 詳細台本を生成"):
    if not yt_key or not gr_key or not hf_key or not my_url:
        st.error("全てのAPIキーとURLを入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            groq_client = Groq(api_key=gr_key)

            # STEP 1: 自分のデータ取得
            with st.spinner("📊 自分のデータを解析中..."):
                my_c_id = None
                if "/channel/" in my_url: my_c_id = my_url.split("/channel/")[1].split("?")[0].split("/")[0]
                elif "/@" in my_url:
                    handle = my_url.split("/@")[1].split("?")[0].split("/")[0]
                    res = youtube.search().list(q=f"@{handle}", type="channel", part="snippet", maxResults=1).execute()
                    if res.get('items'): my_c_id = res['items'][0]['snippet']['channelId']
                
                if not my_c_id:
                    st.error("チャンネルが見つかりませんでした。")
                    st.stop()
                
                my_name, my_df, my_vid = get_channel_data(youtube, my_c_id, "自分")

            # STEP 2: 競合を自動検索
            with st.spinner("🕵️ 市場から競合を自動選別中..."):
                search_query = my_df['タイトル'].iloc[0][:20] if not my_df.empty else "YouTube"
                search_res = youtube.search().list(q=search_query, type="video", part="snippet", maxResults=5).execute()
                
                rival_dfs = [my_df]
                rival_names = []
                found_c_ids = {my_c_id}

                for item in search_res.get('items', []):
                    r_c_id = item['snippet']['channelId']
                    if r_c_id not in found_c_ids:
                        r_name, r_df, _ = get_channel_data(youtube, r_c_id, "競合")
                        if r_df is not None:
                            rival_dfs.append(r_df)
                            rival_names.append(r_name)
                            found_c_ids.add(r_c_id)
                        if len(rival_names) >= 2: break
                
                all_df = pd.concat(rival_dfs, ignore_index=True)

            # STEP 3: 詳細台本執筆 (プロンプト強化)
            with st.spinner("✍️ プロの構成作家が台本を執筆中..."):
                try:
                    c_res = youtube.commentThreads().list(videoId=my_vid, part='snippet', maxResults=15).execute()
                    comments = "\n".join([i['snippet']['topLevelComment']['snippet']['textDisplay'] for i in c_res['items']])
                except: comments = "コメントなし"
                
                prompt = f"""
                あなたはYouTube登録者100万人超のチャンネルを手掛けるトップ構成作家です。
                以下のデータを元に、視聴者が1秒も離脱できない『完全台本』を執筆してください。

                【自社データ】\n{my_df.to_string()}
                【視聴者の声】\n{comments}
                【競合状況】\n{all_df[all_df['区分']=='競合'].to_string()}

                ---執筆ルール---
                1. ターゲット: どんな悩みを持つ人が、この動画でどう変わるか。
                2. コンセプト: 視聴者が思わずクリックする「動画の正体」。
                3. 完全台本（ナレーション原稿）: 
                   - [0:00-0:15 フック] 冒頭で視聴者の心を掴む強烈な一言。
                   - [0:15-1:00 導入] 期待感を最大化するトーク。
                   - [本編] 飽きさせない3章構成。具体的なセリフを「語り口調」で。
                   - [エンディング] 登録へ繋げる自然な誘導。
                4. 演出指示: テロップのタイミングや、BGMの切り替え指示。
                5. サムネ用パワーワード5選。
                """
                report = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

            # STEP 4: 画像生成
            with st.spinner("🎨 サムネイル案を生成中..."):
                image_bytes = generate_image(f"Viral YouTube thumbnail about {my_df['タイトル'].iloc[0]}", hf_key)

            # STEP 5: 表示
            st.success(f"✅ 戦略レポート ＆ 台本が完成しました！")
            t1, t2, t3 = st.tabs(["📄 プロの完全台本", "📊 競合比較・市場分析", "🖼️ サムネイル案"])
            
            with t1:
                st.markdown(report)
            with t2:
                fig = px.bar(all_df, x='再生数', y='タイトル', color='区分', barmode='group', orientation='h', title="競合比較")
                st.plotly_chart(fig, use_container_width=True)
                st.write("### 競合選出されたチャンネル")
                st.table(all_df[['チャンネル', '区分']].drop_duplicates())
            with t3:
                if image_bytes: st.image(Image.open(io.BytesIO(image_bytes)))

        except Exception as e:
            st.error(f"エラー: {e}")
