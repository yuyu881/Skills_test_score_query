"""
 程式功能簡介：Streamlit 後台儀表板主程式 (處理登入、Session 狀態、側邊欄導覽)
 程式歷次修改簡說：2026-03-05/V1.0 - 初始建立
 使用的 Pin 腳/IO：無
 建立者：User & Gemini
 最後一次修改日期：2026-03-05
"""

import streamlit as st
from utils import init_supabase, verify_password

# 設定整體的網頁配置
st.set_page_config(
    page_title="學科成績報表系統",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 Session 狀態
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

# 初始化資料庫連線
try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"資料庫連線失敗，請檢查 .streamlit/secrets.toml 設定。錯誤訊息: {e}")
    st.stop()


def login():
    """顯示登入畫面並處理驗證邏輯"""
    st.title("📚 技能檢定學科成績 - 教師後台")
    st.markdown("---")
    st.subheader("請登入以存取系統")

    with st.form("login_form"):
        username = st.text_input("帳號 (Username)")
        password = st.text_input("密碼 (Password)", type="password")
        submitted = st.form_submit_button("登入 Login")

        if submitted:
            if not username or not password:
                st.warning("請輸入帳號與密碼！")
                return

            try:
                # 查詢資料庫，比對帳號
                response = supabase.table("teachers_auth").select("*").eq("username", username).execute()
                users = response.data

                if len(users) == 0:
                    st.error("找不到此帳號！")
                else:
                    user_record = users[0]
                    stored_hash = user_record["hashed_password"]
                    role = user_record["role"]

                    # 驗證密碼
                    if verify_password(password, stored_hash):
                        # 檢查帳號是否被停用 (相容舊有資料沒有 is_active 欄位的情況，預設為 True)
                        is_active = user_record.get("is_active", True)
                        if not is_active:
                            st.error("此帳號已被管理員停用，請聯絡系統管理員！")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.session_state.role = role
                            st.success(f"登入成功！歡迎，{role} - {username}")
                            st.rerun()  # 重新執行腳本以載入主畫面
                    else:
                        st.error("密碼錯誤！")

            except Exception as e:
                 st.error(f"系統發生錯誤，請聯絡管理員: {e}")


def logout():
    """處理登出邏輯"""
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

# 主程式邏輯路由
if not st.session_state.logged_in:
    login()
else:
    # 已登入狀態，顯示側邊欄導覽
    with st.sidebar:
        st.write(f"👤 您好，**{st.session_state.username}**")
        st.write(f"🔑 權限層級：`{st.session_state.role}`")
        if st.button("🚪 登出系統"):
            logout()
            
    # 這裡的寫法是 Streamlit 的 Multi-page apps 機制。
    # 只要在 pages/ 資料夾下有檔案，Streamlit 會自動生成側邊欄連結。
    # app.py 本身只負責登入保護，如果已登入，我們引導他點擊側邊欄，
    # 或是直接顯示一個歡迎首頁。
    
    st.title("首頁概覽")
    st.info("👈 請從左側選單選擇您要使用的功能。")
    st.markdown("""
    ### 系統功能說明
    * **📊 成績報表查詢**：所有授權教師皆可使用。支援檢視成績、上傳 Excel 名單進行動態比對、以及匯出報表。
    * **⚙️ 系統管理**：僅超級管理員 (Super Admin) 可見。可新增或刪除教師帳號，並修改密碼。
    """)
