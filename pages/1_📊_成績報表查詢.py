"""
 程式功能簡介：Streamlit 後台報表查詢 (V2.1 支援座號排序與列印)
 程式歷次修改簡說：2026-03-07/V2.1 - 加入座號 (seat_number) 顯示，並預設按班級與座號排序，優化列印排版。
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

st.title("📊 學科測驗成績報表 (V2.1)")
st.markdown("系統已根據您的教師帳號，自動載入您專屬的學生名單與成績！")

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
df_roster["座號"] = pd.to_numeric(df_roster["seat_number"], errors='coerce').fillna(0).astype(int) # 轉為數字方便排序

# ----------------------------------------
# 區塊二：側邊欄篩選條件
# ----------------------------------------
st.sidebar.header("🔍 篩選條件")

unique_classes = df_roster["班級"].unique().tolist()
class_options = ["全部班級 (All)"] + sorted(unique_classes)
selected_class = st.sidebar.selectbox("🏫 選擇班級", class_options)

exam_type_options = ["工業電子丙級", "數位電子乙級", "全部 (All)"]
selected_type_label = st.sidebar.selectbox("📖 選擇職類", exam_type_options)

if "工業電子丙級" in selected_type_label:
    type_filter = "classC"
elif "數位電子乙級" in selected_type_label:
    type_filter = "classB"
else:
    type_filter = "All"

exam_scope_filter = st.sidebar.text_input("📄 測驗範圍關鍵字 (如: 題組 1)", "")

# 取代原本寫死的 60 分，讓老師自訂
pass_score = st.sidebar.number_input("💯 及格分數", min_value=0, max_value=100, value=60)

refresh_btn = st.sidebar.button("🔄 重新載入成績")

# 依據老師在側邊欄選擇的班級，即時過濾名單
if selected_class != "全部班級 (All)":
    df_roster_filtered = df_roster[df_roster["班級"] == selected_class].copy()
else:
    df_roster_filtered = df_roster.copy()

# ----------------------------------------
# 區塊三：從 Supabase 撈取成績並合併 (自動比對)
# ----------------------------------------
@st.cache_data(ttl=60)
def fetch_scores(filter_type, filter_scope):
    """與名單無關，單純依照條件把分數庫的東西撈出來"""
    query = supabase.table("score_records").select("*")
    if filter_type != "All":
        query = query.eq("exam_type", filter_type)
    if filter_scope:
       query = query.ilike("exam_scope", f"%{filter_scope}%")
    query = query.order("backend_timestamp", desc=True)
    response = query.execute()
    return response.data

with st.spinner('從 Supabase 取得成績資料中...'):
    if refresh_btn:
        st.cache_data.clear()
    raw_data = fetch_scores(type_filter, exam_scope_filter)

# 準備成績 DataFrame
if raw_data:
    df_scores = pd.DataFrame(raw_data)
    df_display = df_scores[["student_id", "exam_score", "exam_scope", "exam_type", "backend_timestamp"]].copy()
    df_display.columns = ["學號", "分數", "測驗範圍", "職類", "繳交時間"]
    
    # 替換職類名稱
    df_display["職類"] = df_display["職類"].replace({"classC": "工業電子丙級", "classB": "數位電子乙級"})
    
    # 每位學生只保留最新一次的測驗紀錄
    df_latest_scores = df_display.sort_values(by="繳交時間", ascending=False).drop_duplicates(subset=["學號"])
    df_latest_scores["學號"] = df_latest_scores["學號"].astype(str)
else:
    df_latest_scores = pd.DataFrame(columns=["學號", "分數", "測驗範圍", "職類", "繳交時間"])

# 【核心功能】：自動名單比對
# 把過濾好的 df_roster_filtered (主表) 與 df_latest_scores (副表) 利用學號進行 Left Join
final_df = pd.merge(df_roster_filtered[["班級", "座號", "學號", "姓名"]], df_latest_scores, on="學號", how="left")

# 排序：先按班級，再按座號
final_df = final_df.sort_values(by=["班級", "座號"], ascending=[True, True])

# 填補沒考的學生空缺，以及轉型小數點
def format_score(val):
    try:
        if pd.isna(val):
            return "尚未作答"
        return f"{float(val):.2f}"
    except:
        return val

final_df["分數"] = final_df["分數"].apply(format_score)
final_df["測驗範圍"] = final_df["測驗範圍"].fillna("-")
final_df["繳交時間"] = final_df["繳交時間"].apply(lambda x: pd.to_datetime(x).strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else "-")
final_df["職類"] = final_df["職類"].fillna("-")


# ----------------------------------------
# 區塊四：報表顯示與紅字標記
# ----------------------------------------
st.subheader("📝 成績總覽")

def color_score(val):
    """小於自訂的及格分數顯示紅字，大於等於則為綠字，尚未作答為灰字"""
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
# 區塊五：報表匯出功能 (Excel 與 JavaScript 列印/PDF)
# ----------------------------------------
st.subheader("📥 匯出與列印")
col1, col2 = st.columns([1, 1])

# 1. 下載 Excel
def to_excel(df):
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='成績報表')
    return output.getvalue()

excel_data = to_excel(final_df)
with col1:
    st.download_button(
        label="📊 下載 Excel 報表",
        data=excel_data,
        file_name='學科測驗成績報表_V2.1.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        use_container_width=True
    )

# 2. 列印/匯出 PDF (JavaScript 注入法)
html_table = final_df.to_html(index=False, classes="print-table")

custom_print_html = f"""
    <html>
    <head>
    <style>
        .print-table {{
            border-collapse: collapse;
            width: 100%;
            font-family: sans-serif;
            font-size: 14px;
        }}
        .print-table th, .print-table td {{
            border: 1px solid #777;
            text-align: center;
            padding: 8px;
        }}
        .print-table th {{
            background-color: #f2f2f2;
        }}
        .print-table tr {{
            page-break-inside: avoid;
        }}
        @media print {{
            .no-print {{ display: none !important; }}
            @page {{ size: A4 portrait; margin: 1.5cm; }}
        }}
    </style>
    </head>
    <body>
        <div style="text-align: center; margin-bottom: 20px;">
            <h2>📝 學生學科成績列印報表</h2>
            <button onclick="window.print()" class="no-print" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background-color: #4CAF50; color: white; border: none; border-radius: 4px; font-weight: bold;">
                🖨️ 點此開啟列印 / 存檔為 PDF
            </button>
        </div>
        {html_table}
    </body>
    </html>
"""

with col2:
    with st.popover("🖨️ 列印 / 存為 PDF", use_container_width=True):
        st.info("點擊下方預覽表單中的綠色按鈕，即可呼叫您的實體印表機或選擇另存為 PDF。")
        components.html(custom_print_html, height=450, scrolling=True)
