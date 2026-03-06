"""
 程式功能簡介：Streamlit 後台報表查詢 (撈取 Supabase 成績、Excel 匯入比對、報表呈現與匯出)
 程式歷次修改簡說：2026-03-05/V1.0 - 初始建立
 使用的 Pin 腳/IO：無
 建立者：User & Gemini
 最後一次修改日期：2026-03-05
"""

import streamlit as st
import pandas as pd
from utils import init_supabase

# 若尚未登入，切換回首頁 (app.py) 進行登入
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("請先由首頁登入。")
    st.stop()

st.title("📊 學科測驗成績報表")
st.markdown("在這裡您可以查詢學生的線上測驗成績，也可以上傳您的學生名單 Excel 來比對誰還沒有作答。")

# 初始化 Supabase
try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"資料庫連線失敗: {e}")
    st.stop()

# ----------------------------------------
# 區塊一：側邊欄篩選條件
# ----------------------------------------
st.sidebar.header("🔍 篩選條件")

# 職類篩選 (下拉選單選項從資料庫撈取，或者寫死常用選項)
# 這裡採用從 score_records 中的 exam_type 抓出 Distinct 值，或是直接給定預設
exam_type_options = ["classC (丙級)", "classB (乙級)", "全部 (All)"]
selected_type_label = st.sidebar.selectbox("📖 選擇職類", exam_type_options)

if "classC" in selected_type_label:
    type_filter = "classC"
elif "classB" in selected_type_label:
    type_filter = "classB"
else:
    type_filter = "All"

# 測驗範圍篩選 (關鍵字輸入)
exam_scope_filter = st.sidebar.text_input("📄 測驗範圍關鍵字 (如: 題組 1)", "")

# 重新查詢按鈕
refresh_btn = st.sidebar.button("🔄 重新載入成績")


# ----------------------------------------
# 區塊二：從 Supabase 撈取成績
# ----------------------------------------
@st.cache_data(ttl=60)  # 快取 60 秒，避免頻繁呼叫 API
def fetch_scores(filter_type, filter_scope):
    """撈取並整理學生成績"""
    query = supabase.table("score_records").select("*")
    
    # 加入職類 Filter
    if filter_type != "All":
        query = query.eq("exam_type", filter_type)
        
    # 加入範圍 Filter (Supabase 的 ilike 支援模糊搜尋)
    if filter_scope:
       query = query.ilike("exam_scope", f"%{filter_scope}%")
       
    # 以時間排序 (最新的在最上面)
    query = query.order("backend_timestamp", desc=True)
    
    response = query.execute()
    return response.data

# 呼叫撈取函式
with st.spinner('從 Supabase 取得資料中...'):
    if refresh_btn:
        st.cache_data.clear() # 若使用者按重新載入，清除快取
    raw_data = fetch_scores(type_filter, exam_scope_filter)

# 轉換為 pandas DataFrame 以方便處理
if not raw_data:
    st.info("目前沒有符合設定條件的成績資料。")
    st.stop()

df_scores = pd.DataFrame(raw_data)

# 這裡為了報表清楚，整理/重新命名欄位
# 欄位 mapping: student_id, student_name, exam_score, exam_scope, backend_timestamp
df_display = df_scores[["student_id", "student_name", "exam_score", "exam_scope", "exam_type", "backend_timestamp"]].copy()
df_display.columns = ["學號", "姓名", "分數", "測驗範圍", "職類", "繳交時間"]

# 若時間為 ISO 格式，可轉換為較好讀的字串
df_display["繳交時間"] = pd.to_datetime(df_display["繳交時間"]).dt.strftime('%Y-%m-%d %H:%M:%S')


# ----------------------------------------
# 區塊三：名單比對 (Upload Excel)
# ----------------------------------------
st.subheader("📋 學生繳交狀態比對 (選填)")
st.info("""
**💡 上傳名單自動比對說明：**  
若您上傳學生名冊，系統會自動幫您過濾出「哪些學生還沒有進行測驗 / 哪些學生不及格」。

**【Excel/CSV 檔案格式要求】**
1. **必備欄位：** 標題列 (第一列) 必須包含 **名稱為 `學號` 與 `姓名`** 的兩個欄位。
2. **無順序性：** 欄位順序不拘，系統會自動由名稱抓取。
3. **其他欄位：** 檔案內若有班級、座號、科系等欄位，可直接保留，比對後會原封不動顯示在畫面上供您參考！
""")

uploaded_file = st.file_uploader("上傳 Excel 或 CSV 檔案", type=["xlsx", "xls", "csv"])

# 要呈現的最終 DataFrame (預設為全部成績)
final_df = df_display.copy()

if uploaded_file is not None:
    # 讀取名單
    try:
        if uploaded_file.name.endswith('.csv'):
            df_roster = pd.read_csv(uploaded_file)
        else:
            df_roster = pd.read_excel(uploaded_file)
            
        # 檢查必備欄位
        if "學號" not in df_roster.columns or "姓名" not in df_roster.columns:
            st.error("上傳的名單檔案中必須包含名為『學號』與『姓名』的欄位！")
        else:
            st.success("✅ 名單上傳成功！已執行自動比對。")
            
            # 使用我們原本的成績 df_display，針對每個學生，只保留最新的一筆成績
            # (避免同一個學生重複測驗，比對時出現重複紀錄)
            df_latest_scores = df_display.sort_values(by="繳交時間", ascending=False).drop_duplicates(subset=["學號"])
            
            # 將 roster (主表) Left Join scores
            # 學號必須轉成 string 以防 Excel 讀為數字而比對失敗
            df_roster["學號"] = df_roster["學號"].astype(str)
            df_latest_scores["學號"] = df_latest_scores["學號"].astype(str)
            
            # 合併
            final_df = pd.merge(df_roster, df_latest_scores[["學號", "分數", "測驗範圍", "繳交時間"]], on="學號", how="left")
            
            # 填補空值
            final_df["分數"] = final_df["分數"].fillna("尚未作答")
            final_df["測驗範圍"] = final_df["測驗範圍"].fillna("-")
            final_df["繳交時間"] = final_df["繳交時間"].fillna("-")
            
    except Exception as e:
        st.error(f"讀取名單檔案失敗: {e}")


# ----------------------------------------
# 區塊四：報表顯示與紅字標記
# ----------------------------------------
st.subheader("📝 成績總覽")

# 定義上色的 Function (Pandas Styler)
def color_score(val):
    """小於 60 分顯示紅字，大於等於 60 為綠字，尚未作答為灰字"""
    if val == "尚未作答":
        color = "gray"
    else:
        try:
            score = float(val)
            color = "red" if score < 60 else "green"
        except:
            color = "black"
    return f"color: {color}; font-weight: bold;"

# 顯示資料表 (使用 Styler 讓分數上色)
styled_df = final_df.style.map(color_score, subset=["分數"])

# 在畫面上渲染
st.dataframe(styled_df, use_container_width=True, height=500)

# ----------------------------------------
# 區塊五：報表匯出功能
# ----------------------------------------
def to_excel(df):
    """將 DataFrame 轉為 Excel binary format，供下載"""
    import io
    output = io.BytesIO()
    # 使用 xlsxwriter 引擎 (pandas 內建支援)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='成績報表')
    processed_data = output.getvalue()
    return processed_data

excel_data = to_excel(final_df)

st.download_button(
    label="🔽 下載報表 (Excel 格式)",
    data=excel_data,
    file_name='學科測驗成績報表.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
)
