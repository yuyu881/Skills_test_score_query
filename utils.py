"""
 程式功能簡介：Streamlit 後台儀表板共用工具 (Supabase 連線、密碼雜湊驗證)
 程式歷次修改簡說：2026-03-05/V1.0 - 初始建立
 使用的 Pin 腳/IO：無
 建立者：User & Gemini
 最後一次修改日期：2026-03-05
"""

import streamlit as st
from supabase import create_client, Client
import bcrypt

@st.cache_resource
def init_supabase() -> Client:
    """初始化並快取 Supabase 客戶端連線"""
    # 支援新舊版 Streamlit 對 secrets.toml [secrets] 標頭的解析差異
    try:
        if "secrets" in st.secrets:
            url = st.secrets["secrets"]["SUPABASE_URL"]
            key = st.secrets["secrets"]["SUPABASE_SERVICE_ROLE_KEY"]
        else:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
            
        return create_client(url, key)
    except KeyError as e:
        raise Exception(f"找不到 Supabase 金鑰設定 ({e})，請確認 .streamlit/secrets.toml 格式正確。")

def hash_password(password: str) -> str:
    """密碼加密 (用於未來新增帳號)"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """驗證密碼是否正確"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
