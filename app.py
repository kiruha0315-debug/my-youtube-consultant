import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from groq import Groq
from openai import OpenAI  # 画像生成用に追加

# --- ページ設定 ---
st.set_page_config(page_title="AI動画 究極コンサル V2", layout="wide", page_icon="🎨")
st.title("🎨 AI動画 究極コンサル & サムネイル生成")

# --- API設定 ---
with st.sidebar:
    st.header("🔑 API設定")
    yt_key = st.text_input("YouTube API Key", value=st.secrets.get("YOUTUBE_API_KEY", ""), type="password")
    gr_key = st.text_input("Groq API Key", value=st.secrets.get("GROQ_API_KEY", ""), type="password")
    oa_key = st.text_input("OpenAI API Key (画像生成用)", value=st.secrets.get("OPENAI_API_KEY", ""), type="password")
    st.info("OpenAI Keyを入れるとサムネイル画像が生成されます。")

url = st.text_input("分析したいYouTubeチャンネルのURL")

if st.button("🚀 戦略・台本・サムネイルを一括生成"):
    if not yt_key or not gr_key or not url:
        st.error("APIキーとURLを正しく入力してください。")
    else:
        try:
            youtube = build('youtube', 'v3', developerKey=yt_key)
            
            # --- 1. チャンネル・動画データ取得 (前回同様) ---
            with st.spinner("📊 データを収集中..."):
                # (チャンネルID特定・動画取得ロジックは前回と同じため省略)
                # 変数 df に動画データが入っている前提
                pass # ここに前回の取得ロジックが入ります

            # --- 2. AIによる戦略・台本・SEO作成 ---
            with st.spinner("🧠 AIが戦略とSEOデータを執筆中..."):
                groq_client = Groq(api_key=gr_key)
                prompt = f"""
                YouTubeプロデューサーとして回答してください。
                データ: {df.to_string() if 'df' in locals() else '新規チャンネル'}

                依頼:
                1.【企画案】次作のタイトル1案
                2.【台本】ショート用と通常動画用のダブル台本
                3.【SEO最適化】
                   - 検索されやすい説明文(概要欄)
                   - 最適なハッシュタグ5つ
                   - 関連キーワードタグ
                4.【画像プロンプト】サムネイル画像生成AI用の詳細な英語指示文
                """
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                report = completion.choices[0].message.content
                
                # AIの回答から画像プロンプトを抽出（簡易的な抽出ロジック）
                image_prompt = report.split("画像プロンプト")[-1].strip()

            # --- 3. 【新機能】サムネイル画像生成 ---
            generated_image_url = None
            if oa_key:
                with st.spinner("🎨 サムネイル画像を生成中..."):
                    oa_client = OpenAI(api_key=oa_key)
                    img_response = oa_client.images.generate(
                        model="dall-e-3",
                        prompt=f"YouTube thumbnail for: {image_prompt}. High contrast, vibrant colors, catchy, no text.",
                        size="1024x1024",
                        quality="standard",
                        n=1,
                    )
                    generated_image_url = img_response.data[0].url

            # --- 4. 結果表示 ---
            st.success("✅ 全ての生成が完了しました！")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("💡 戦略・台本・SEO")
                st.markdown(report)
            
            with col2:
                if generated_image_url:
                    st.subheader("🖼️ サムネイル案")
                    st.image(generated_image_url, caption="AI生成サムネイルイメージ")
                    st.info("※文字は画像編集ソフト（Canvaなど）で後から追加してください。")
                
                st.subheader("🏷️ コピペ用タグ")
                st.code("#AI動画 #生成AI #YouTube戦略", language="text")

        except Exception as e:
            st.error(f"エラー: {e}")
