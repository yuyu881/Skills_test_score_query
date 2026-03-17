"""
 程式功能簡介：Streamlit 後台 - 學生名冊管理 (由 Admin 負責批次匯入包含教師與班級資訊的 Excel)
 程式歷次修改簡說：
 2026-03-07/V2.1 - 新增座號 (seat_number) 欄位支援，調整範本欄位順序。
 2026-03-17/V2.2 - 優化 Excel 匯入預覽畫面，明確顯示總筆數並維持前 5 筆預覽。
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

st.title("🗂️ 學生名冊集中管理 (V2.1)")
st.markdown("請在此處上傳全校/跨班的學生名單。系統將依據您指定的「**指導教師帳號**」，將學生分發給對應的老師。")

# 初始化 Supabase
try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"資料庫連線失敗: {e}")
    st.stop()

# ----------------------------------------
# 區塊一：下載範本與格式說明
# ----------------------------------------
st.info("""
**💡 上傳名單批次匯入說明：**  
請準備一份 Excel 檔案 (副檔名 .xlsx, .xls 或 .csv)。

**【嚴格必備的 5 個標題欄位】 (名稱必須完全一致，建議照順序)：**
1. `班級` (如: 電子一)
2. `學號` (如: 911001) - **此為系統唯一識別碼，若重複上傳同個學號，將會覆寫更新資料**。
3. `座號` (如: 1)
4. `姓名` (如: 王小明)
5. `指導教師帳號` (如: teacher01)
""")

# 產生範本 DataFrame 讓管理員下載
template_df = pd.DataFrame({
    "班級": ["電子一", "電子一", "電子二"],
    "學號": ["911001", "911002", "921001"],
    "座號": [1, 2, 1],
    "姓名": ["王大明", "陳小華", "林阿呆"],
    "指導教師帳號": ["teacher01", "teacher01", "teacher02"]
})

# 轉換為 Excel 格式提供下載
import io
output = io.BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    template_df.to_excel(writer, index=False, sheet_name='名單匯入範本')
excel_data = output.getvalue()

st.download_button(
    label="🔽 下載 Excel 名單標準範本 (V2.1 座號版)",
    data=excel_data,
    file_name='學生名單匯入範本_V2.1.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
)

st.divider()

# ----------------------------------------
# 區塊二：檔案上傳與匯入邏輯
# ----------------------------------------
uploaded_file = st.file_uploader("上傳含有學生名單的 Excel 檔案", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_roster = pd.read_csv(uploaded_file, dtype={"學號": str, "座號": str})
        else:
            df_roster = pd.read_excel(uploaded_file, dtype={"學號": str, "座號": str})
            
        # 檢查 5 個必備欄位
        required_columns = ["班級", "學號", "座號", "姓名", "指導教師帳號"]
        missing_cols = [col for col in required_columns if col not in df_roster.columns]
        
        if missing_cols:
            st.error(f"❌ 匯入失敗！您的檔案缺少以下必備欄位：{', '.join(missing_cols)}")
        else:
            st.success("✅ 檔案格式檢查通過，請確認資料後點擊下方按鈕寫入資料庫。")
            
            # 預覽前 5 筆與顯示總筆數
            st.write(f"📂 準備匯入總筆數：**{len(df_roster)}** 筆。以下僅預覽前 5 筆資料：")
            st.dataframe(df_roster.head(5), use_container_width=True)
            
            # 確認寫入按鈕
            if st.button("🚀 確認匯入並更新至資料庫", type="primary"):
                with st.spinner('正在寫入資料庫，請稍候...'):
                    # 準備整理要送進 Supabase 的資料格式 (List of Dicts)
                    records_to_upsert = []
                    
                    # 刪除所有有空值的列 (避免有空白格被傳進去)
                    df_clean = df_roster.dropna(subset=required_columns)
                    
                    for index, row in df_clean.iterrows():
                        records_to_upsert.append({
                            "student_id": str(row["學號"]).strip(),
                            "student_name": str(row["姓名"]).strip(),
                            "class_name": str(row["班級"]).strip(),
                            "teacher_username": str(row["指導教師帳號"]).strip(),
                            "seat_number": row["座號"] # 新增座號
                        })
                    
                    # 批次送進 Supabase 的 Upsert
                    if not records_to_upsert:
                         st.warning("檔案中沒有有效的資料列。")
                    else:
                        response = supabase.table("student_roster").upsert(records_to_upsert).execute()
                        st.success(f"🎉 匯入成功！共寫入/更新了 {len(records_to_upsert)} 筆學生資料！")
                        st.balloons()
                
    except Exception as e:
        st.error(f"檔案解析或匯入失敗: {e}")
