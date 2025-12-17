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
st.set_page_config(page_title="YouTube AI Command Center AUTO", layout="wide", page_icon="🚀")
st.title("🚀 YouTube AI 運営司令塔 (競合自動リサーチ強化版)")

# --- 2. API設定 (サイドバー) ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    hf_key = st.text_input("Hugging Face Token", value=st.secrets.get("HF_TOKEN", ""), type="password")

# --- 3. 画像生成関数 ---
def generate_image(prompt, token):
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {token}"}
    for i in range(2):
        try:
            response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=30)
            if response.status_code == 200: return response.content
            elif response.status_code == 503: time.sleep(20); continue
        except: continue
    return None

# --- 4. チャンネルデータ取得関数 (より確実にデータを取るように修正) ---
def get_channel_data(youtube, c_id, label="対象"):
    try:
        ch_res = youtube.channels().list(id=c_id, part='snippet,contentDetails').execute()
        if not ch_res.get('items'):
            return None, None, None
            
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
        
        if not v_data:
            return title, pd.DataFrame(), None
            
        return title, pd.DataFrame(v_data), v_ids[0]
    except Exception as e:
        st.warning(f"チャンネル {c_id} のデータ取得に失敗: {e}")
        return None, None, None

# --- 5. メイン入力エリア ---
my_url = st.text_input("あなたのチャンネルURLを入力してください")

if st.button("🛰️ 自動リサーチ＆戦略立案を開始"):
    if not yt_key or not gr_key or not hf_key or not my_url:
        st.error("全てのAPIキーとURLを入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            groq_client = Groq(api_key=gr_key)

            # --- STEP 1: 自分のデータ取得 ---
            with st.spinner("📊 あなたのデータを解析中..."):
                my_c_id = None
                if "/channel/" in my_url: my_c_id = my_url.split("/channel/")[1].split("?")[0].split("/")[0]
                elif "/@" in my_url:
                    handle = my_url.split("/@")[1].split("?")[0].split("/")[0]
                    res = youtube.search().list(q=f"@{handle}", type="channel", part="snippet", maxResults=1).execute()
                    if res.get('items'): my_c_id = res['items'][0]['snippet']['channelId']
                
                if not my_c_id:
                    st.error("自分のチャンネルIDが特定できませんでした。URLを確認してください。")
                    st.stop()
                
                my_name, my_df, my_vid = get_channel_data(youtube, my_c_id, "自分")

            # --- STEP 2: 競合を自動検索 (検索ロジックを強化) ---
            with st.spinner("🕵️ 市場から競合ライバルを検索中..."):
                # 最新動画のタイトルから検索キーワードを抽出
                search_query = my_df['タイトル'].iloc[0][:20] if not my_df.empty else "YouTube"
                # 動画検索を行い、ヒットした動画の「投稿者（チャンネル）」をリストアップ
                search_res = youtube.search().list(q=search_query, type="video", part="snippet", maxResults=5).execute()
                
                rival_dfs = [my_df]
                rival_names = []
                found_c_ids = set() # 重複防止

                for item in search_res.get('items', []):
                    r_c_id = item['snippet']['channelId']
                    if r_c_id != my_c_id and r_c_id not in found_c_ids:
                        r_name, r_df, _ = get_channel_data(youtube, r_c_id, "競合")
                        if r_df is not None and not r_df.empty:
                            rival_dfs.append(r_df)
                            rival_names.append(r_name)
                            found_c_ids.add(r_c_id)
                        if len(rival_names) >= 2: break # 競合は2つ程度で制限

                all_df = pd.concat(rival_dfs, ignore_index=True)

            # --- STEP 3: コメント分析 & 戦略立案 ---
            with st.spinner("🧠 AIが戦略を練っています..."):
                # コメント取得
                try:
                    c_res = youtube.commentThreads().list(videoId=my_vid, part='snippet', maxResults=15).execute()
                    comments = "\n".join([i['snippet']['topLevelComment']['snippet']['textDisplay'] for i in c_res['items']])
                except:
                    comments = "コメントが取得できませんでした。"
                
                rival_list_str = ", ".join(rival_names) if rival_names else "自動検出中"
                prompt = f"""
                YouTubeプロデューサーとして指示します。
                【比較データ】\n{all_df.to_string()}
                【自社コメント】\n{comments}
                【比較対象の競合名】: {rival_list_str}
                
                1. 競合と比較した自社の立ち位置分析。
                2. 競合動画から盗める「伸びる要素」。
                3. クリック率を上げるサムネイル用ワード（5案）。
                4. 冒頭のフック（3パターン）。
                5. 次回動画の構成。
                """
                report = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content

            # --- STEP 4: 画像生成 ---
            with st.spinner("🎨 サムネイル案を作成中..."):
                image_bytes = generate_image(f"Eye-catching YouTube thumbnail about {my_df['タイトル'].iloc[0] if not my_df.empty else 'Success'}", hf_key)

            # --- STEP 5: 表示 ---
            st.success(f"✅ リサーチ完了！ (競合: {rival_list_str})")
            t1, t2, t3 = st.tabs(["💎 AI戦略コンサル", "📊 競合比較グラフ", "🖼️ サムネイル案"])
            
            with t1:
                st.markdown(report)
            with t2:
                # グラフの表示
                fig = px.bar(all_df, x='再生数', y='タイトル', color='区分', barmode='group', orientation='h', 
                             hover_data=['チャンネル'], title="競合との再生数比較")
                st.plotly_chart(fig, use_container_width=True)
                
                st.write("### 取得されたチャンネル一覧")
                st.dataframe(all_df[['区分', 'チャンネル', 'タイトル', '再生数']].drop_duplicates('チャンネル'))
                
            with t3:
                if image_bytes: st.image(Image.open(io.BytesIO(image_bytes)))

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
