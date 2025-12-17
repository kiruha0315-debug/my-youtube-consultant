import streamlit as st
import pandas as pd
import plotly.express as px  # グラフ用に追加
from googleapiclient.discovery import build
from groq import Groq
from openai import OpenAI

# --- ページ設定 ---
st.set_page_config(page_title="YouTube AI Analytics", layout="wide", page_icon="📈")
st.title("📈 YouTube 動画別詳細分析 & AIコンサル")

# --- API設定 (サイドバー) ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    oa_key = st.text_input("OpenAI API Key", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")

url = st.text_input("分析したいチャンネルURL")

if st.button("📊 詳細分析を開始"):
    if not yt_key or not gr_key or not url:
        st.error("APIキーとURLを入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            
            # --- 1. データ取得 ---
            with st.spinner("データを取得中..."):
                # (前回のロジックでチャンネルID特定)
                # ... [中略: チャンネルID特定処理] ...
                
                # 動画詳細データの取得（投稿日、再生数、高評価、コメント数を取得）
                # ... [中略: playlistItemsから動画リスト取得] ...
                
                # 仮のデータフレーム作成例 (実際はAPIから取得した値が入ります)
                # df = pd.DataFrame(video_data)
                # df['高評価率'] = (df['高評価'] / df['再生数'] * 100).round(2)
                
            # --- 2. グラフ表示セクション ---
            st.header("📊 パフォーマンス可視化")
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.subheader("動画別再生数の比較")
                # 横棒グラフで各動画の再生数を比較
                fig = px.bar(df, x='再生数', y='タイトル', orientation='h', 
                             color='再生数', color_continuous_scale='Reds',
                             title="最新10本の再生数比較")
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                st.subheader("エンゲージメント分析")
                # 散布図で「再生数」と「高評価率」の関係を表示
                fig2 = px.scatter(df, x='再生数', y='高評価率', size='高評価',
                                  hover_name='タイトル', title="再生数 vs 高評価率")
                st.plotly_chart(fig2, use_container_width=True)

            # --- 3. 1本ごとの詳細カード表示 ---
            st.header("🔍 動画別詳細レポート")
            for index, row in df.iterrows():
                with st.expander(f"【{index+1}】 {row['タイトル']}"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("再生数", f"{row['再生数']:,}回")
                    c2.metric("高評価数", f"{row['高評価']:,}件")
                    c3.metric("高評価率", f"{row['高評価率']}%")
                    
                    # AIによる個別アドバイス（簡易版）
                    if row['再生数'] > df['再生数'].mean():
                        st.success("🌟 この動画は平均より伸びています！このテーマのシリーズ化を検討しましょう。")
                    else:
                        st.warning("💡 この動画は伸び悩んでいます。サムネイルのクリック率を確認してください。")

            # --- 4. AI戦略レポート (台本・SEO・画像) ---
            # (前回の Groq & OpenAI 処理)

        except Exception as e:
            st.error(f"エラー: {e}")

# --- requirements.txt に plotly を追加してください ---
