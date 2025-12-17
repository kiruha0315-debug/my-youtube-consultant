import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from groq import Groq

# 1. ページの設定
st.set_page_config(page_title="AI動画コンサルタント", layout="wide", page_icon="🤖")

# --- タイトル・説明 ---
st.title("🤖 AI動画 YouTubeコンサルタント")
st.markdown("チャンネルURLを入力するだけで、最新データに基づいた戦略をAIが提案します。")

# --- サイドバー (API設定) ---
with st.sidebar:
    st.header("🔑 API設定")
    # Streamlit CloudのSecretsから取得するか、直接入力
    yt_key = st.text_input("YouTube API Key", 
                           value=st.secrets.get("YOUTUBE_API_KEY", ""), 
                           type="password")
    gr_key = st.text_input("Groq API Key", 
                           value=st.secrets.get("GROQ_API_KEY", ""), 
                           type="password")
    st.info("APIキーを保存したい場合は、Streamlit CloudのSettings > Secretsに設定してください。")

# --- メイン入力エリア ---
url = st.text_input("分析したいYouTubeチャンネルのURL", placeholder="https://www.youtube.com/@handle")

if st.button("AI戦略を生成する"):
    if not yt_key or not gr_key:
        st.error("APIキーが設定されていません。サイドバーから入力してください。")
    elif not url:
        st.warning("チャンネルURLを入力してください。")
    else:
        try:
            # YouTube API サービスの構築
            youtube = build('youtube', 'v3', developerKey=yt_key)
            
            # 1. チャンネルIDの特定
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
                st.error("チャンネルが見つかりませんでした。URLが正しいか確認してください。")
            else:
                # 2. 動画データの取得
                with st.spinner("📊 最新の動画データを取得中..."):
                    ch_res = youtube.channels().list(id=c_id, part='contentDetails').execute()
                    playlist_id = ch_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    
                    pl_res = youtube.playlistItems().list(playlistId=playlist_id, part='snippet', maxResults=10).execute()
                    
                    video_data = []
                    for item in pl_res['items']:
                        v_id = item['snippet']['resourceId']['videoId']
                        v_res = youtube.videos().list(id=v_id, part='snippet,statistics').execute()['items'][0]
                        
                        video_data.append({
                            'タイトル': v_res['snippet']['title'],
                            '再生数': int(v_res['statistics'].get('viewCount', 0)),
                            '高評価': int(v_res['statistics'].get('likeCount', 0)),
                            '投稿日': v_res['snippet']['publishedAt'][:10]
                        })
                    df = pd.DataFrame(video_data)

                # 3. Groq AI による分析
                with st.spinner("🧠 AIコンサルタントが戦略を立案中..."):
                    groq_client = Groq(api_key=gr_key)
                    summary = df.to_string(index=False)
                    
                    prompt = f"""
                    あなたはYouTubeチャンネル「AI動画生成場」の戦略コンサルタントです。
                    以下のデータに基づき、プロフェッショナルな回答をしてください。

                    ### チャンネルデータ（最新10本）
                    {summary}

                    ### 依頼内容
                    1. ヒット傾向の分析（どの動画がなぜ伸びているか）
                    2. 次に作るべき「AI動画」のタイトル案を3つ
                    3. 各案に対して「ショート」か「通常動画」かの推奨とその理由
                    4. 各案の「爆速テロップ案（ショート）」または「高CTRサムネイル文字案（通常）」
                    5. 映像生成AI（Luma/Runway等）で使える英語プロンプト
                    """
                    
                    completion = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": "あなたはYouTube分析のプロフェッショナルです。日本語で親切かつ具体的に回答してください。"},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7
                    )
                    report = completion.choices[0].message.content

                # 4. 結果表示
                st.success("✅ 分析が完了しました！")
                
                # レポートをタブで表示
                tab1, tab2 = st.tabs(["💡 戦略レポート", "📊 生データ"])
                with tab1:
                    st.markdown(report)
                with tab2:
                    st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")
