"""
 程式功能簡介：Streamlit 後台報表查詢 (V2.3 教師專屬範圍選單與座號排序)
 程式歷次修改簡說：2026-03-07/V2.3 - 優化選單：測驗範圍選單僅顯示該教師所屬學生曾經考過的項目，避免看到他班資訊。
 使用的 Pin 腳/IO：無
 建立者：User & Gemini
 最後一次修改日期：2026-03-07
"""

import streamlit as st
import pandas as pd
from utils import init_supabase
import streamlit.components.v1 as components

# 若尚未登入，切換回首頁 (app.py) 進行登入
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.warning("請先由首頁登入。")
    st.stop()

st.title("📊 學科測驗成績報表 (V2.3)")
st.markdown("系統已根據您的教師帳號，自動過濾您專屬的學生名單與可選測驗範圍！")

# 初始化 Supabase
try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"資料庫連線失敗: {e}")
    st.stop()

username = st.session_state.username
role = st.session_state.role

# ----------------------------------------
# 區塊一：撈取專屬學生名單
# ----------------------------------------
@st.cache_data(ttl=60)
def fetch_roster(usr, r):
    """依據權限撈取名冊，Admin可見全部，Teacher只見自己麾下名單"""
    query = supabase.table("student_roster").select("*")
    if r != "admin":
        query = query.eq("teacher_username", usr)
    response = query.execute()
    return response.data

with st.spinner('載入專屬學生名冊中...'):
    roster_data = fetch_roster(username, role)

if not roster_data:
    st.info("目前系統中沒有指派給您的學生名單，或是尚未匯入。請聯絡系統管理員 (Admin) 於左側選單進行名冊匯入。")
    st.stop()

df_roster = pd.DataFrame(roster_data)
# 整理 roster 欄位名稱
df_roster["學號"] = df_roster["student_id"].astype(str)
df_roster["姓名"] = df_roster["student_name"]
df_roster["班級"] = df_roster["class_name"]
df_roster["座號"] = pd.to_numeric(df_roster["seat_number"], errors='coerce').fillna(0).astype(int)

# ----------------------------------------
# 區塊二：撈取「該教師學生」現有的「測驗範圍」供選單使用
# ----------------------------------------
@st.cache_data(ttl=120)
def fetch_available_scopes_v23(student_ids, r):
    """
    從 score_records 撈取不重複的測驗範圍。
    V2.3 改進：如果不是 Admin，則只撈取 list 中學生的成績範圍。
    """
    query = supabase.table("score_records").select("exam_scope")
    
    # 如果不是 Admin，則加上學生 ID 過濾 (Supabase .in_ 語法)
    if r != "admin" and student_ids:
        query = query.in_("student_id", student_ids)
        
    response = query.execute()
    if response.data:
        scopes = sorted(list(set(item["exam_scope"] for item in response.data if item["exam_scope"])))
        return scopes
    return []

# 取得目前名冊中所有學生的 ID 清單
my_student_ids = df_roster["學號"].tolist()
available_scopes = fetch_available_scopes_v23(my_student_ids, role)

# ----------------------------------------
# 區塊三：側邊欄篩選條件
# ----------------------------------------
st.sidebar.header("🔍 篩選條件")

unique_classes = df_roster["班級"].unique().tolist()
class_options = ["全部班級 (All)"] + sorted(unique_classes)
selected_class = st.sidebar.selectbox("🏫 選擇班級預覽", class_options)

exam_type_options = ["工業電子丙級", "數位電子乙級", "全部 (All)"]
selected_type_label = st.sidebar.selectbox("📖 選擇職類預閱", exam_type_options)

if "工業電子丙級" in selected_type_label:
    type_filter = "classC"
elif "數位電子乙級" in selected_type_label:
    type_filter = "classB"
else:
    type_filter = "All"

# 改用 selectbox
scope_options = ["全部範圍 (All)"] + available_scopes
selected_scope = st.sidebar.selectbox("📄 選擇測驗範圍", scope_options)

# 及格分數設定
pass_score = st.sidebar.number_input("💯 及格門檻分數", min_value=0, max_value=100, value=60)

refresh_btn = st.sidebar.button("🔄 重新載入資料")

# 依據老師在側邊欄選擇的班級，即時過濾名單
if selected_class != "全部班級 (All)":
    df_roster_filtered = df_roster[df_roster["班級"] == selected_class].copy()
else:
    df_roster_filtered = df_roster.copy()

# ----------------------------------------
# 區塊四：從 Supabase 撈取成績並合併 (自動比對)
# ----------------------------------------
@st.cache_data(ttl=60)
def fetch_scores(filter_type, filter_scope):
    """依照條件撈取分數庫資料"""
    query = supabase.table("score_records").select("*")
    if filter_type != "All":
        query = query.eq("exam_type", filter_type)
    if filter_scope != "全部範圍 (All)":
        query = query.eq("exam_scope", filter_scope)
        
    query = query.order("backend_timestamp", desc=True)
    response = query.execute()
    return response.data

with st.spinner('比對成績資料中...'):
    if refresh_btn:
        st.cache_data.clear()
        st.rerun()
    raw_data = fetch_scores(type_filter, selected_scope)

# 準備成績 DataFrame
if raw_data:
    df_scores = pd.DataFrame(raw_data)
    df_scores_working = df_scores[["student_id", "exam_score", "exam_scope", "exam_type", "backend_timestamp"]].copy()
    df_scores_working.columns = ["學號", "分數", "測驗範圍", "職類", "繳交時間"]
    
    # 替換職類名稱顯示
    df_scores_working["職類"] = df_scores_working["職類"].replace({"classC": "工業電子丙級", "classB": "數位電子乙級"})
    
    # 每位學生只保留該範圍內最新一次的測驗紀錄
    df_latest_scores = df_scores_working.sort_values(by="繳交時間", ascending=False).drop_duplicates(subset=["學號"])
    df_latest_scores["學號"] = df_latest_scores["學號"].astype(str)
else:
    df_latest_scores = pd.DataFrame(columns=["學號", "分數", "測驗範圍", "職類", "繳交時間"])

# 【核心功能】：自動名單比對
final_df = pd.merge(df_roster_filtered[["班級", "座號", "學號", "姓名"]], df_latest_scores, on="學號", how="left")

# 排序：先按班級，再按座號
final_df = final_df.sort_values(by=["班級", "座號"], ascending=[True, True])

# 填補沒考的學生空缺，以及格式化
def format_score(val):
    try:
        if pd.isna(val) or val == "尚未作答":
            return "尚未作答"
        return f"{float(val):.2f}"
    except:
        return val

final_df["分數"] = final_df["分數"].apply(format_score)
final_df["測驗範圍"] = final_df["測驗範圍"].fillna("-")
final_df["繳交時間"] = final_df["繳交時間"].apply(lambda x: pd.to_datetime(x).strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) and x != "-" else "-")
final_df["職類"] = final_df["職類"].fillna("-")


# ----------------------------------------
# 區塊五：報表顯示與紅字標記
# ----------------------------------------
st.subheader("📝 成績報表總覽")

def color_score(val):
    """及格與否顏色標記"""
    if val == "尚未作答":
        color = "gray"
    else:
        try:
            score = float(val)
            color = "red" if score < pass_score else "green"
        except:
            color = "black"
    return f"color: {color}; font-weight: bold;"

styled_df = final_df.style.map(color_score, subset=["分數"])
st.dataframe(styled_df, use_container_width=True, height=600)


# ----------------------------------------
# 區塊六：匯出與原創列印
# ----------------------------------------
st.subheader("📥 匯出或列印")
col1, col2 = st.columns([1, 1])

# 1. 下載 Excel
def to_excel(df):
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='成績表')
    return output.getvalue()

excel_data = to_excel(final_df)
with col1:
    st.download_button(
        label="📊 下載 Excel 報表",
        data=excel_data,
        file_name=f'成績報表_{selected_class}_{selected_scope}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        use_container_width=True
    )

# 2. 列印/匯出 PDF
html_table = final_df.to_html(index=False, classes="print-table")
custom_print_html = f"""
    <html>
    <head>
    <style>
        .print-table {{ border-collapse: collapse; width: 100%; font-family: sans-serif; font-size: 14px; }}
        .print-table th, .print-table td {{ border: 1px solid #777; text-align: center; padding: 8px; }}
        .print-table th {{ background-color: #f2f2f2; }}
        @media print {{ .no-print {{ display: none !important; }} @page {{ size: A4 portrait; margin: 1.5cm; }} }}
    </style>
    </head>
    <body>
        <div style="text-align: center; margin-bottom: 20px;">
            <h2>📝 學生學科測驗成績報表</h2>
            <p>班級：{selected_class} | 測驗職類：{selected_type_label} | 測驗範圍：{selected_scope}</p>
            <button onclick="window.print()" class="no-print" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background-color: #4CAF50; color: white; border: none; border-radius: 4px; font-weight: bold;">
                🖨️ 列印此頁或另存為 PDF
            </button>
        </div>
        {html_table}
    </body>
    </html>
"""

with col2:
    with st.popover("🖨️ 產生列印視窗", use_container_width=True):
        st.write("點擊下方綠色按鈕開啟瀏覽器列印對話框：")
        components.html(custom_print_html, height=500, scrolling=True)
