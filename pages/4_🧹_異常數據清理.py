"""
 程式功能簡介：Streamlit 後台 - 異常數據清理 (僅限 Admin，清理不在學生名冊中的成績)
 程式歷次修改簡說：2026-03-07/V2.5 - 新格頁面：實作自動比對學號並提供批次刪除功能。
 使用的 Pin 腳/IO：無
 建立者：User & Gemini
 最後一次修改日期：2026-03-07
"""

import streamlit as st
import pandas as pd
from utils import init_supabase

# 1. 權限檢查：必須登入，且必須是 admin
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("請先由首頁登入。")
    st.stop()
    
# 如果目前登入者不是 admin，直接阻擋
if st.session_state.get("role") != "admin":
    st.error("權限不足：您必須是系統管理員 (Admin) 才能存取此頁面。")
    st.stop()

st.title("🧹 異常成績紀錄清理 (Admin Only)")
st.markdown("""
本頁面會自動比對 **成績紀錄 (ScoreRecords)** 與 **學生名冊 (StudentRoster)**。  
若成績紀錄中的「學號」不在正式名冊內，將被列為「異常數據」。
""")

# 初始化 Supabase
try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"資料庫連線失敗: {e}")
    st.stop()

# ----------------------------------------
# 區塊一：資料比對邏輯
# ----------------------------------------
@st.cache_data(ttl=30)
def find_anomalies():
    """找出不在名冊內的成績紀錄"""
    # 1. 撈取所有成績
    res_scores = supabase.table("score_records").select("*").execute()
    df_scores = pd.DataFrame(res_scores.data) if res_scores.data else pd.DataFrame()
    
    # 2. 撈取所有正式學號
    res_roster = supabase.table("student_roster").select("student_id").execute()
    valid_ids = [item["student_id"] for item in res_roster.data] if res_roster.data else []
    
    if df_scores.empty:
        return pd.DataFrame(), []

    # 3. 比對：學號不在有效名單內的
    df_anomalies = df_scores[~df_scores["student_id"].isin(valid_ids)].copy()
    
    # 格式化顯示
    if not df_anomalies.empty:
        df_anomalies["backend_timestamp"] = pd.to_datetime(df_anomalies["backend_timestamp"]).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_anomalies = df_anomalies.sort_values(by="backend_timestamp", ascending=False)
        
    return df_anomalies, df_anomalies["id"].tolist()

with st.spinner('正在比對異常數據...'):
    df_bad, bad_ids = find_anomalies()

# ----------------------------------------
# 區塊二：介面呈現
# ----------------------------------------
if df_bad.empty:
    st.success("🎉 太棒了！目前系統中所有成績皆屬於正式名冊內的學生，無異常數據。")
    if st.button("🔄 重新整理"):
        st.cache_data.clear()
        st.rerun()
else:
    st.warning(f"⚠️ 偵測到 {len(df_bad)} 筆異常成績紀錄 (學號未在名冊中)。")
    
    # 顯示列表
    display_df = df_bad[["student_id", "student_name", "exam_scope", "exam_score", "backend_timestamp", "exam_type"]]
    display_df.columns = ["學號", "姓名", "測驗範圍", "分數", "時間", "職類"]
    st.dataframe(display_df, use_container_width=True, height=400)

    st.divider()

    # ----------------------------------------
    # 區塊三：刪除功能 (含二次確認)
    # ----------------------------------------
    st.subheader("🗑️ 危險操作區")
    st.error("注意：刪除操作不可逆，請務必確認上方清單皆為廢棄或錯誤數據。")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # 使用 popover 做二次確認
        with st.popover("🔥 刪除所有清單內的異常紀錄", use_container_width=True):
            st.write(f"您確定要刪除這 {len(bad_ids)} 筆紀錄嗎？")
            confirm_code = st.text_input("請輸入 'DELETE' 以確認執行", "")
            
            if st.button("🔴 確認永久刪除", type="primary", use_container_width=True):
                if confirm_code == "DELETE":
                    try:
                        # 批次刪除 (Supabase .in_ 語法)
                        # 注意：如果數量極大建議分批，但異常成績通常不多
                        res = supabase.table("score_records").delete().in_("id", bad_ids).execute()
                        st.success(f"✅ 已成功刪除 {len(bad_ids)} 筆異常資料！")
                        st.cache_data.clear()
                        st.balloons()
                        # 延遲一點點後重整
                        st.info("頁面將在 2 秒後自動重新整理...")
                        import time
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"刪除失敗: {e}")
                else:
                    st.warning("請輸入正確的確認碼。")
    
    with col2:
        if st.button("🔄 重新比對", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
