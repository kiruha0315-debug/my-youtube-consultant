import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from groq import Groq

# --- ページ設定 ---
st.set_page_config(page_title="AI動画 究極コンサル", layout="wide", page_icon="🔥")
st.title("🔥 AI動画 YouTube究極コンサルタント")
st.markdown("自分のURLを入れるだけで、**競合を自動リサーチし、ショートと通常動画の両方の台本**を作成します。")

# --- API設定 (Secretsまたはサイドバー) ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")

url = st.text_input("分析したいYouTubeチャンネルのURL", placeholder="https://www.youtube.com/@handle")

if st.button("🚀 競合比較 ＆ 両方の台本を生成"):
    if not yt_key or not gr_key or not url:
        st.error("APIキーとURLを正しく入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            
            # 1. チャンネルID特定
            with st.spinner("🔍 チャンネルを特定中..."):
                c_id = None
                if "/channel/" in url:
                    c_id = url.split("/channel/")[1].split("?")[0].split("/")[0]
                elif "/@" in url:
                    handle = url.split("/@")[1].split("?")[0].split("/")[0]
                    res = youtube.search().list(q=f"@{handle}", type="channel", part="snippet", maxResults=1).execute()
                    if res.get('items'): c_id = res['items'][0]['snippet']['channelId']
            
            if not c_id:
                st.error("チャンネルが見つかりませんでした。")
            else:
                # 2. 自チャンネルデータ取得
                with st.spinner("📊 自チャンネルのデータを取得中..."):
                    ch_res = youtube.channels().list(id=c_id, part='snippet,contentDetails').execute()
                    ch_title = ch_res['items'][0]['snippet']['title']
                    playlist_id = ch_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    pl_res = youtube.playlistItems().list(playlistId=playlist_id, part='snippet', maxResults=10).execute()
                    
                    v_data = []
                    for item in pl_res['items']:
                        v_id = item['snippet']['resourceId']['videoId']
                        v_res = youtube.videos().list(id=v_id, part='snippet,statistics').execute()['items'][0]
                        v_data.append({
                            'タイトル': v_res['snippet']['title'],
                            '再生数': int(v_res['statistics'].get('viewCount', 0)),
                            'タグ': ",".join(v_res['snippet'].get('tags', []))
                        })
                    df = pd.DataFrame(v_data)

                # 3. 【新機能】競合チャンネルを自動特定してリサーチ
                with st.spinner("🛰️ 競合チャンネルを自動リサーチ中..."):
                    # 自チャンネルの最新タイトルをキーワードに競合検索
                    keyword = df['タイトル'].iloc[0][:15]
                    search_res = youtube.search().list(q=keyword, type="channel", part="snippet", maxResults=2).execute()
                    
                    comp_info = []
                    for item in search_res.get('items', []):
                        cid = item['snippet']['channelId']
                        cname = item['snippet']['title']
                        # 競合のトップ動画を1本
                        top_v = youtube.search().list(channelId=cid, part='snippet', order='viewCount', maxResults=1).execute()
                        if top_v['items']:
                            v_title = top_v['items'][0]['snippet']['title']
                            comp_info.append(f"競合名: {cname} (代表作: {v_title})")

                # 4. AIによる戦略立案 & 台本生成
                with st.spinner("🧠 AIが最強の戦略と台本を執筆中..."):
                    groq_client = Groq(api_key=gr_key)
                    prompt = f"""
                    あなたはYouTube登録者100万人の現役プロデューサーです。
                    
                    ### データ
                    - 分析対象: {ch_title}
                    - 最新動画データ: {df.to_string()}
                    - リサーチされた競合: {", ".join(comp_info)}

                    ### 依頼
                    1. 【競合比較分析】: 競合に勝てるポイントを3点。
                    2. 【爆伸び企画案】: 次に作るべき企画のタイトル案。
                    3. 【台本A：ショート動画(60秒)】: 
                       - 視聴維持率を下げない爆速展開の台本。
                       - ナレーション内容、テロップ、AI映像への指示をセットで。
                    4. 【台本B：通常動画(8分程度)】: 
                       - 導入(フック)・本編(深掘り)・結末の構成。
                       - 視聴者が「最後まで見てしまう」仕掛けを含めた詳細なプロット。
                    5. 【映像生成用プロンプト】: どちらでも使える英語プロンプト。
                    """
                    
                    completion = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "system", "content": "プロのYouTubeディレクターとして、具体的で即戦力になる回答を日本語で作成してください。"},
                                  {"role": "user", "content": prompt}],
                        temperature=0.7
                    )
                    report = completion.choices[0].message.content

                # 5. 結果表示
                st.success("✅ 全ての戦略と台本が完成しました！")
                
                tab1, tab2, tab3 = st.tabs(["🚀 戦略 & 台本レポート", "🔍 比較データ", "📈 自データ"])
                with tab1:
                    st.markdown(report)
                with tab2:
                    st.subheader("自動特定された競合")
                    for c in comp_info: st.write(f"- {c}")
                with tab3:
                    st.dataframe(df)

        except Exception as e:
            st.error(f"エラー: {e}")
