"""
 程式功能簡介：Streamlit 後台系統管理 (新增帳號、刪除帳號)
 程式歷次修改簡說：2026-03-05/V1.0 - 初始建立
 使用的 Pin 腳/IO：無
 建立者：User & Gemini
 最後一次修改日期：2026-03-05
"""

import streamlit as st
import pandas as pd
from utils import init_supabase, hash_password

# 安全性檢查：確認已登入且為 administrator
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("請先由首頁登入。")
    st.stop()

if st.session_state.role != "admin":
    st.error("您沒有權限存取此頁面！這需要超級管理員權限。")
    st.stop()

st.title("⚙️ 系統管理 (帳號權限控制)")
st.markdown("最高權限管理員可以在此處新增或移除其他教師的系統存取帳號。")

# 初始化 Supabase
try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"資料庫連線失敗: {e}")
    st.stop()

# ----------------------------------------
# 區塊一：新增教師帳號
# ----------------------------------------
with st.expander("➕ 新增教師帳號", expanded=True):
    with st.form("add_user_form", clear_on_submit=True):
        new_username = st.text_input("輸入新帳號名稱 (Username)", placeholder="例如：teacher123")
        new_password = st.text_input("輸入初始密碼 (Password)", type="password")
        # 支援建立 teacher 或 admin 權限
        new_role = st.selectbox("帳號層級", ["teacher", "admin"], help="admin：可管理所有帳號；teacher：僅能檢視報表")
        
        submit_add = st.form_submit_button("建立帳號")
        
        if submit_add:
            if not new_username or not new_password:
                st.error("帳號與密碼欄位不可為空！")
            else:
                # 檢查帳號是否已存在
                check_exist = supabase.table("teachers_auth").select("username").eq("username", new_username).execute()
                if len(check_exist.data) > 0:
                    st.error(f"建立失敗：帳號 `{new_username}` 已存在！")
                else:
                    # 密碼加密並寫入資料庫
                    hashed_pw = hash_password(new_password)
                    insert_data = {
                        "username": new_username,
                        "hashed_password": hashed_pw,
                        "role": new_role,
                        "is_active": True # 預設為啟用
                    }
                    result = supabase.table("teachers_auth").insert(insert_data).execute()
                    if result.data:
                        st.success(f"✅ 成功為 `{new_username}` 建立 `{new_role}` 帳號！")
                        # 因為 Streamlit 狀態更新需要 rerender，用空按鈕或重整也可以，這裡直接刷新
                        st.rerun()
                    else:
                         st.error("建立帳號失敗，請聯絡系統開發人員。")


st.markdown("---")

# ----------------------------------------
# 區塊二：目前帳號清單與刪除操作
# ----------------------------------------
st.subheader("📋 目前授權帳號清單")

@st.cache_data(ttl=5) # 短暫快取
def fetch_users():
    resp = supabase.table("teachers_auth").select("id", "username", "role", "is_active", "created_at").execute()
    return resp.data

users_data = fetch_users()

if not users_data:
    st.info("系統尚無任何帳號。")
else:
    # 呈現為 pandas dataframe 較美觀
    df_users = pd.DataFrame(users_data)
    
    # 處理可能沒有 is_active 欄位的舊資料 (相容性)
    if "is_active" not in df_users.columns:
        df_users["is_active"] = True
        
    # 將時間轉為台北時間
    df_users["created_at"] = pd.to_datetime(df_users["created_at"]).dt.tz_convert('Asia/Taipei').dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 將 boolean 轉換為可讀的文字
    df_users["狀態"] = df_users["is_active"].apply(lambda x: "✅ 啟用中" if x else "❌ 已停用")
    
    # 調整欄位順序與名稱
    df_display = df_users[["id", "username", "role", "狀態", "created_at"]]
    df_display.columns = ["編號 (ID)", "帳號名稱", "權限層級", "帳號狀態", "建立時間"]
    st.dataframe(df_display, hide_index=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    # 帳號狀態切換功能
    with col1:
        with st.expander("🛑 停用 / 啟用 教師帳號", expanded=True):
            # 不允許切換自己 (防止 admin 鎖死自己)
            target_list_status = [u["username"] for u in users_data if u["username"] != st.session_state.username]
            if not target_list_status:
                 st.info("目前無其他帳號可供切換狀態。")
            else:
                 target_user_status = st.selectbox("選擇要變更狀態的帳號", target_list_status, key="status_select")
                 
                 # 找出該帳號目前的狀態
                 current_status = next((u.get("is_active", True) for u in users_data if u["username"] == target_user_status), True)
                 new_status_text = "停用 (禁止登入)" if current_status else "重新啟用 (允許登入)"
                 btn_type = "primary" if not current_status else "secondary"
                 
                 if st.button(f"🔄 設為『{new_status_text}』", type=btn_type):
                      update_resp = supabase.table("teachers_auth").update({"is_active": not current_status}).eq("username", target_user_status).execute()
                      if update_resp.data:
                          st.success(f"已成功將 `{target_user_status}` 的狀態變更為：{new_status_text}！")
                          fetch_users.clear() # 清除快取強制更新
                          st.rerun()
                      else:
                          st.error("狀態變更失敗。")

    # 刪除功能
    with col2:
        with st.expander("🗑️ 永久刪除 教師帳號", expanded=True):
            # 為防誤刪，不允許刪除自己
            target_list_del = [u["username"] for u in users_data if u["username"] != st.session_state.username]
            
            if not target_list_del:
                st.info("目前無『teacher』層級的帳號可供刪除。")
            else:
                del_username = st.selectbox("選擇要刪除的帳號", target_list_del, key="del_select")
                # 確認機制
                confirm_del = st.checkbox(f"我確認要永久刪除帳號 `{del_username}`。此操作無法復原。")
                if st.button("🗑️ 執行刪除", type="primary", disabled=not confirm_del):
                    del_resp = supabase.table("teachers_auth").delete().eq("username", del_username).execute()
                    if del_resp.data:
                        st.success(f"已成功刪除 `{del_username}` 的存取權限！")
                        fetch_users.clear() # 清除快取強制更新
                        st.rerun()
                    else:
                        st.error("刪除失敗。")
