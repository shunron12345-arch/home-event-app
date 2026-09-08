import calendar
from datetime import datetime, date
import time
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# ページの基本設定
st.set_page_config(
    page_title="予約アプリ", page_icon="🏠", layout="centered"
)

# スマホファースト用カスタムCSS
st.markdown("""
    <style>
    /* Streamlitのデフォルトヘッダーを非表示にする */
    [data-testid="stHeader"] {
        display: none !important;
    }

    .block-container {
        max-width: 480px !important;
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    h1 {
        font-size: 1.4rem !important;
        font-weight: bold !important;
        padding-bottom: 0.5rem !important;
    }

    h2, h3 {
        font-size: 1.1rem !important;
        font-weight: bold !important;
    }

    /* 7列カレンダーグリッドの崩れ防止 */
    [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(3):last-child)) {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 2px !important;
    }
    [data-testid="stHorizontalBlock"]:not(:has(> [data-testid="stColumn"]:nth-child(3):last-child)) > [data-testid="stColumn"] {
        flex: 1 !important;
        min-width: 0 !important;
        width: calc(100% / 7) !important;
    }

    /* ボタン共通のベーススタイル */
    div[data-testid="stButton"] button {
        border-radius: 6px;
        border: 2px solid #e2e8f0;
        background: #ffffff;
        color: #1e293b;
        font-weight: 700;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    }

    /* カレンダー内の日付ボタン等のスタイル */
    div[data-testid="stColumn"] div[data-testid="stButton"] button {
        width: 100% !important;
        height: auto !important;
        min-height: 68px !important;
        max-height: 68px !important;
        padding: 4px 1px !important;
        font-size: 0.6rem !important;
        line-height: 1.15 !important;
        white-space: pre-wrap !important;
        word-break: break-all !important;
        overflow-wrap: break-word !important;
        box-sizing: border-box !important;
    }

    div[data-testid="stColumn"] div[data-testid="stButton"] button div,
    div[data-testid="stColumn"] div[data-testid="stButton"] button p,
    div[data-testid="stColumn"] div[data-testid="stButton"] button span {
        white-space: pre-wrap !important;
        word-break: break-all !important;
        overflow-wrap: break-word !important;
        text-overflow: clip !important;
        overflow: visible !important;
        display: block !important;
        width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)

weekdays = ["月", "火", "水", "木", "金", "土", "日"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def init_connection():
  if "gcp_service_account" in st.secrets:
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
  else:
    creds = Credentials.from_service_account_file(
        "credentials.json", scopes=SCOPES
    )
  client = gspread.authorize(creds)
  sheet = client.open("予約アプリ")
  return sheet

try:
  sheet = init_connection()
except Exception as e:
  st.error(f"スプレッドシートへの接続に失敗しました: {e}")
  st.stop()

def send_reservation_email(date_str, content_str, user_name):
  try:
    if "email" in st.secrets:
      sender_email = st.secrets["email"]["sender_email"]
      app_password = st.secrets["email"]["app_password"]
    else:
      return

    recipient_email = "shunron12345@gmail.com"
    subject = f"【予約通知】{user_name}様から新規予約が入りました"
    body = (
        f"新しい予約が登録されました。\n\n"
        f"・日付: {date_str}\n"
        f"・イベント: {content_str}\n"
        f"・お名前: {user_name}様\n\n"
        f"確認をお願いします。"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender_email
    msg["To"] = recipient_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
      server.login(sender_email, app_password)
      server.sendmail(sender_email, [recipient_email], msg.as_string())
  except Exception as e:
    print(f"メール送信エラー: {e}")

# キャッシュを手動クリアできるように変更 (st.cache_dataのクリア)
def load_data_from_sheet():
  try:
    schedules_data = sheet.worksheet("schedules").get_all_records()
    reservations_data = sheet.worksheet("reservations").get_all_records()
    lessons_data = sheet.worksheet("lessons").get_all_records()
    
    try:
      memos_data = sheet.worksheet("memos").get_all_records()
    except Exception:
      memos_data = []

    df_schedules = (
        pd.DataFrame(schedules_data)
        if schedules_data
        else pd.DataFrame(columns=["id", "date", "content", "capacity"])
    )
    if not df_schedules.empty and "content" in df_schedules.columns:
      df_schedules["content"] = (
          df_schedules["content"]
          .astype(str)
          .str.replace(r"^[①②③④⑤⑥⑦⑧⑨⑩\d]+[\.\s]*", "", regex=True)
      )

    df_reservations = (
        pd.DataFrame(reservations_data)
        if reservations_data
        else pd.DataFrame(columns=["id", "date", "content", "name"])
    )
    if not df_reservations.empty and "content" in df_reservations.columns:
      df_reservations["content"] = (
          df_reservations["content"]
          .astype(str)
          .str.replace(r"^[①②③④⑤⑥⑦⑧⑨⑩\d]+[\.\s]*", "", regex=True)
      )

    df_lessons = (
        pd.DataFrame(lessons_data)
        if lessons_data
        else pd.DataFrame(
            columns=["id", "title", "body", "image_urls", "video_url", "status"]
        )
    )

    df_memos = (
        pd.DataFrame(memos_data)
        if memos_data
        else pd.DataFrame(columns=["id", "date", "content"])
    )

    return df_schedules, df_reservations, df_lessons, df_memos
  except Exception as e:
    st.error(f"データの読み込み中にエラーが発生しました: {e}")
    return (
        pd.DataFrame(columns=["id", "date", "content", "capacity"]),
        pd.DataFrame(columns=["id", "date", "content", "name"]),
        pd.DataFrame(columns=["id", "title", "body", "image_urls", "video_url", "status"]),
        pd.DataFrame(columns=["id", "date", "content"]),
    )

@st.cache_data(ttl=60)
def load_data_cached():
  return load_data_from_sheet()

df_schedules, df_reservations, df_lessons, df_memos = load_data_cached()

if "my_name" not in st.session_state:
  st.session_state.my_name = ""

if "current_menu" not in st.session_state:
  st.session_state.current_menu = "📅 予約カレンダー"

# 画面上部の共通ナビゲーションバー
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)
with nav_col1:
  if st.button("📅\n予約", use_container_width=True, key="nav_cal"):
    st.session_state.current_menu = "📅 予約カレンダー"
    st.rerun()
with nav_col2:
  if st.button("👤\n確認", use_container_width=True, key="nav_my"):
    st.session_state.current_menu = "👤 自分の予約・変更"
    st.rerun()
with nav_col3:
  if st.button("🥁\n練習", use_container_width=True, key="nav_drum"):
    st.session_state.current_menu = "🥁 ドラム練習用"
    st.rerun()
with nav_col4:
  if st.button("🔐\n管理", use_container_width=True, key="nav_admin"):
    st.session_state.current_menu = "🔐 管理人ページ"
    st.rerun()

st.markdown("""
<div style="font-size: 0.8rem; color: #475569; background-color: #f8fafc; padding: 10px; border-radius: 6px; margin: 10px 0 15px 0; line-height: 1.4;">
<b>【使い方】</b><br>
📅 <b>予約：</b> カレンダーから予約<br>
👤 <b>確認：</b> 予約の確認・キャンセル<br>
🥁 <b>練習：</b> ドラムの楽譜等<br>
🔐 <b>管理：</b> 管理人用
</div>
""", unsafe_allow_html=True)

menu = st.session_state.current_menu

# ---------------------------------------------------------
# 1. 予約カレンダーページ
# ---------------------------------------------------------
if menu == "📅 予約カレンダー":
  st.title("予約カレンダー")
  st.write("日付を選択、フォームに名前を入力して、予約ボタンを押してください。")

  if not df_schedules.empty:
    if not df_reservations.empty:
      res_counts = (
          df_reservations.groupby(["date", "content"])
          .size()
          .reset_index(name="booked_count")
      )
      df_display = pd.merge(
          df_schedules, res_counts, on=["date", "content"], how="left"
      )
      df_display["booked_count"] = df_display["booked_count"].fillna(0).astype(int)
    else:
      df_display = df_schedules.copy()
      df_display["booked_count"] = 0

    df_display["remaining"] = (
        df_display["capacity"] - df_display["booked_count"]
    )

    today_str = datetime.today().strftime("%Y-%m-%d")
    df_display = df_display[df_display["date"] >= today_str]

    if not df_display.empty:
      dates_with_bookings = df_display[df_display["booked_count"] > 0]["date"].unique()
      df_display = df_display[
          (~df_display["date"].isin(dates_with_bookings)) | (df_display["booked_count"] > 0)
      ]
  else:
    df_display = pd.DataFrame(columns=["id", "date", "content", "capacity", "remaining"])

  if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.today().year
  if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.today().month
  if "selected_date" not in st.session_state:
    st.session_state.selected_date = "すべて表示"

  st.markdown(
      f"<div style='font-size: 1.2rem; font-weight: bold; color: #000000; text-align: center; margin-bottom: 10px;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</div>",
      unsafe_allow_html=True,
  )

  cols = st.columns(7)
  for i, day_name in enumerate(weekdays):
    cols[i].markdown(f"<div style='text-align: center; font-weight: bold; color: #db2777; font-size: 0.75rem;'>{day_name}</div>", unsafe_allow_html=True)

  cal_matrix = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
  today_str = datetime.today().strftime("%Y-%m-%d")

  for week in cal_matrix:
    cols = st.columns(7)
    for i, day in enumerate(week):
      with cols[i]:
        if day == 0:
          st.write("")
        else:
          date_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{day:02d}"
          
          day_schedules = df_display[df_display["date"] == date_str] if not df_display.empty else pd.DataFrame()
          has_memo = not df_memos[(df_memos["date"] == date_str) & (df_memos["date"] >= today_str)].empty if not df_memos.empty else False

          if not day_schedules.empty:
            lines = [str(day)]
            for _, sch in day_schedules.iterrows():
              c_text = str(sch["content"])
              if "BBQ" in c_text:
                icon = "🍖"
              elif "ドラム" in c_text:
                icon = "🥁"
              elif "ダーツ" in c_text:
                icon = "🎯"
              else:
                icon = "📌"
              
              rem = sch["remaining"]
              lines.append(f"{icon}{rem}")
            btn_label = "\n".join(lines)
          elif has_memo:
            btn_label = f"{day}\n📝"
          else:
            btn_label = f"{day}"

          is_selected = (st.session_state.selected_date == date_str)
          
          # 選択中の見た目を安全に変更
          btn_type = "primary" if is_selected else "secondary"

          if st.button(btn_label, key=f"cal_day_{date_str}", use_container_width=True, type=btn_type):
            st.session_state.selected_date = date_str
            st.rerun()

  col_prev_btn, col_next_btn = st.columns(2)
  with col_prev_btn:
    if st.button("◀ 前月", key="cal_prev_month", use_container_width=True):
      if st.session_state.cal_month == 1:
        st.session_state.cal_month = 12
        st.session_state.cal_year -= 1
      else:
        st.session_state.cal_month -= 1
      st.rerun()
  with col_next_btn:
    if st.button("次月 ▶", key="cal_next_month", use_container_width=True):
      if st.session_state.cal_month == 12:
        st.session_state.cal_month = 1
        st.session_state.cal_year += 1
      else:
        st.session_state.cal_month += 1
      st.rerun()

  st.markdown(
      "<p style='font-size: 0.75rem; color: #64748b; text-align: center; margin-top: 5px;'>"
      "🥁:ドラム ｜ 🎯:ダーツ ｜ 🍖:BBQ（数字は残り枠） ｜ 📝:メモあり"
      "</p>",
      unsafe_allow_html=True
  )

  if st.button("すべての期間を表示する", use_container_width=True):
    st.session_state.selected_date = "すべて表示"
    st.rerun()

  # 選択された日付のメモがあれば表示するセクション
  if st.session_state.selected_date != "すべて表示" and not df_memos.empty:
    selected_memos = df_memos[df_memos["date"] == st.session_state.selected_date]
    if not selected_memos.empty:
      st.markdown("---")
      st.markdown(f"### 📝 {st.session_state.selected_date} のメモ")
      for _, memo in selected_memos.iterrows():
        st.info(memo["content"])

  st.markdown("---")

  st.subheader("🗓️ 予約申し込み")

  if st.session_state.selected_date != "すべて表示":
    filtered_display = df_display[df_display["date"] == st.session_state.selected_date] if not df_display.empty else pd.DataFrame()
  else:
    filtered_display = df_display

  if filtered_display.empty:
    st.info("イベントの予定はありません")
  else:
    for index, row in filtered_display.iterrows():
      with st.container():
        content_str = str(row["content"])
        if "BBQ" in content_str:
          img_path = "assets/BBQ.jpg"
        elif "ドラム" in content_str:
          img_path = "assets/drums.jpg"
        else:
          img_path = "assets/darts.jpg"

        c_img, c_text = st.columns([1, 2])
        with c_img:
          try:
            st.image(img_path, width=135)
          except Exception:
            pass
        with c_text:
          st.markdown(f"**📅 日付:** {row['date']}")
          st.markdown(f"**🎯 イベント:** {content_str}")

        rem = row["remaining"]
        cap = row["capacity"]
        
        if rem > 0:
          st.markdown(
              f"**🟢 残り枠:** <span style='color:green; font-weight:bold;'>{rem}枠</span> (定員: {cap}名)",
              unsafe_allow_html=True,
          )
        else:
          st.markdown(
              f"**🔴 残り枠:** <span style='color:red; font-weight:bold;'>満席</span> (定員: {cap}名)",
              unsafe_allow_html=Type, # ※そのままコピーする場合は通常の文字列や修正点に注意
          )

        if rem > 0:
          with st.form(key=f"予約form_{row['id']}_{index}"):
            user_name = st.text_input(
                "お名前", value=st.session_state.my_name, key=f"name_{row['id']}_{index}"
            )
            submit = st.form_submit_button("予約する", use_container_width=True)
            if submit:
              entered_name = user_name.strip()
              if entered_name == "":
                st.warning("お名前を入力してください。")
              else:
                already_exists = False
                if not df_reservations.empty:
                  match = df_reservations[
                      (df_reservations["date"] == str(row["date"])) &
                      (df_reservations["content"] == str(row["content"])) &
                      (df_reservations["name"] == entered_name)
                  ]
                  if not match.empty:
                    already_exists = True

                if already_exists:
                  st.warning("すでに予約が入っています。")
                else:
                  st.session_state.my_name = entered_name
                  new_row = [
                      str(row["id"]),
                      str(row["date"]),
                      str(row["content"]),
                      entered_name,
                  ]
                  sheet.worksheet("reservations").append_row(new_row)
                  send_reservation_email(str(row["date"]), str(row["content"]), entered_name)

                  st.cache_data.clear() # キャッシュをクリアして最新化
                  time.sleep(0.5)
                  st.success(f"{row['date']}の【{row['content']}】を予約しました！")
                  time.sleep(1)
                  st.rerun()
        else:
          st.write("❌ 満席です")
        st.markdown(f"---")

# ---------------------------------------------------------
# 2. 自分の予約・変更ページ
# ---------------------------------------------------------
elif menu == "👤 自分の予約・変更":
  st.title("👤 自分の予約一覧・変更")
  st.write("予約時に入力したお名前で、ご自身の予約を確認・キャンセルできます。")

  input_name = st.text_input("お名前を入力して確認", value=st.session_state.my_name)
  
  if input_name:
    st.session_state.my_name = input_name.strip()
    
    if df_reservations.empty:
      st.info("現在、登録されている予約はありません。")
    else:
      my_res = df_reservations[df_reservations["name"] == st.session_state.my_name]
      
      if my_res.empty:
        st.info(f"{st.session_state.my_name}様の予約は見つかりませんでした。")
      else:
        st.success(f"{st.session_state.my_name}様の予約（全 {len(my_res)} 件）")
        
        for idx, res in my_res.iterrows():
          with st.container():
            st.markdown(f"**📅 日付:** {res['date']}")
            st.markdown(f"**🎯 イベント:** {res['content']}")
            
            if st.button("この予約をキャンセルする", key=f"cancel_{res['date']}_{res['content']}_{idx}", use_container_width=True):
              try:
                cell_list = sheet.worksheet("reservations").findall(str(res["name"]))
                target_row = None
                for c in cell_list:
                  row_values = sheet.worksheet("reservations").row_values(c.row)
                  if len(row_values) >= 4 and row_values[1] == str(res["date"]) and row_values[2] == str(res["content"]) and row_values[3] == str(res["name"]):
                    target_row = c.row
                    break
                
                if target_row:
                  sheet.worksheet("reservations").delete_rows(target_row)
                  st.cache_data.clear()
                  time.sleep(0.5)
                  st.success("予約をキャンセルしました。")
                  time.sleep(1)
                  st.rerun()
                else:
                  st.error("該当する予約データの行が見つかりませんでした。")
              except Exception as e:
                st.error(f"キャンセル処理中にエラーが発生しました: {e}")
            st.markdown("---")
  else:
    st.info("お名前を入力すると予約が表示されます。")

# ---------------------------------------------------------
# 3. ドラム練習用
# ---------------------------------------------------------
elif menu == "🥁 ドラム練習用":
  st.title("🥁 楽譜等の置き場")
  st.write("ドラムの楽譜やレッスン動画を確認できます。")

  if df_lessons.empty:
    st.info("まだ公開されている記事はありません。")
  else:
    if "image_urls" not in df_lessons.columns:
      df_lessons["image_urls"] = ""

    published_lessons = df_lessons[df_lessons["status"] == "公開"]
    if published_lessons.empty:
      st.info("現在公開されている記事はありません。")
    else:
      for _, lesson in published_lessons.iterrows():
        st.markdown(f"## 🎵 {lesson['title']}")
        st.write(lesson["body"])

        if lesson["video_url"]:
          st.markdown("### 📺 動画")
          st.video(lesson["video_url"])

        if lesson["image_urls"]:
          st.markdown("### 🖼️ 楽譜等")
          urls = [
              url.strip()
              for url in str(lesson["image_urls"]).split(",")
              if url.strip()
          ]
          if len(urls) > 0:
            if len(urls) == 1:
              st.image(urls[0], use_container_width=True)
            else:
              tabs = st.tabs([f"画像 {i+1}" for i in range(len(urls))])
              for i, tab in enumerate(tabs):
                with tab:
                  st.image(urls[i], use_container_width=True)

        st.markdown("---")

# ---------------------------------------------------------
# 4. 管理人ページ
# ---------------------------------------------------------
elif menu == "🔐 管理人ページ":
  st.title("🔐 管理人ダッシュボード")

  admin_pass = st.text_input("管理人パスワードを入力", type="password")
  if admin_pass == "admin123":
    st.success("認証成功しました！")

    tab_sch, tab_memo, tab_les, tab_res_list = st.tabs(
        ["🗓️ 枠", "📝 メモ", "🥁 資料", "📋 一覧"]
    )

    with tab_sch:
      st.subheader("🗓️ スケジュール追加")
      if "admin_selected_date" not in st.session_state:
        st.session_state.admin_selected_date = datetime.today().date()

      st.markdown(
          f"<div style='font-size: 1.1rem; font-weight: bold; color: #000000; text-align: center; margin-bottom: 10px;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</div>",
          unsafe_allow_html=True,
      )

      cols = st.columns(7)
      for i, day_name in enumerate(weekdays):
        cols[i].markdown(f"<div style='text-align: center; font-weight: bold; color: #64748b; font-size: 0.75rem;'>{day_name}</div>", unsafe_allow_html=True)

      cal_matrix = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)
      for week in cal_matrix:
        cols = st.columns(7)
        for i, day in enumerate(week):
          with cols[i]:
            if day == 0:
              st.write("")
            else:
              date_str = f"{st.session_state.cal_year}-{st.session_state.cal_month:02d}-{day:02d}"
              if st.button(f"{day}", key=f"admin_cal_day_{date_str}", use_container_width=True):
                st.session_state.admin_selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                st.rerun()

      col_aprev_btn, col_anext_btn = st.columns(2)
      with col_aprev_btn:
        if st.button("◀ 前月", key="adm_prev_btn", use_container_width=True):
          if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
          else:
            st.session_state.cal_month -= 1
          st.rerun()
      with col_anext_btn:
        if st.button("次月 ▶", key="adm_next_btn", use_container_width=True):
          if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1
            st.session_state.cal_year += 1
          else:
            st.session_state.cal_month += 1
          st.rerun()

      st.markdown("---")

      def on_content_change():
        content = st.session_state.content_select
        if "ドラム" in content:
          st.session_state.capacity_input = 1
        elif "ダーツ" in content:
          st.session_state.capacity_input = 6
        elif "BBQ" in content:
          st.session_state.capacity_input = 4

      if "content_select" not in st.session_state:
        st.session_state.content_select = "ドラム"
      if "capacity_input" not in st.session_state:
        st.session_state.capacity_input = 1

      new_date = st.date_input("開催日", value=st.session_state.admin_selected_date)
      new_content = st.selectbox(
          "コンテンツ",
          ["ドラム", "ダーツ", "BBQ"],
          key="content_select",
          on_change=on_content_change
      )
      new_capacity = st.number_input(
          "定員数",
          min_value=1,
          key="capacity_input"
      )

      if st.button("枠を追加する", use_container_width=True):
        sched_id = str(int(time.time()))
        sheet.worksheet("schedules").append_row(
            [sched_id, str(new_date), new_content, int(new_capacity)]
        )
        st.cache_data.clear()
        time.sleep(0.5)
        st.success(f"{new_date} に枠を追加しました！")
        time.sleep(1)
        st.rerun()

      st.markdown("---")
      st.subheader("スケジュール一覧・編集・削除")
      if not df_schedules.empty:
        schedule_options = {
            f"{row['date']} - {row['content']} (定員:{row['capacity']})": row
            for _, row in df_schedules.iterrows()
        }
        selected_sched_key = st.selectbox(
            "編集・削除する枠を選択", list(schedule_options.keys()), key="edit_sched_select"
        )

        if selected_sched_key:
          selected_sched_row = schedule_options[selected_sched_key]
          sched_sel_id = str(selected_sched_row["id"])

          # 更新用フォームと削除用ボタンを分離して誤動作を防ぐ
          with st.form(f"edit_sched_form_{sched_sel_id}"):
            try:
              curr_date = datetime.strptime(str(selected_sched_row["date"]), "%Y-%m-%d").date()
            except Exception:
              curr_date = datetime.today().date()

            e_sched_date = st.date_input("開催日", value=curr_date)
            
            contents = ["ドラム", "ダーツ", "BBQ"]
            curr_content = str(selected_sched_row["content"])
            curr_content_idx = contents.index(curr_content) if curr_content in contents else 0
            e_sched_content = st.selectbox("コンテンツ", contents, index=curr_content_idx)
            
            try:
              curr_cap = int(selected_sched_row["capacity"])
            except Exception:
              curr_cap = 4
            e_sched_capacity = st.number_input("定員数", min_value=1, value=curr_cap)

            update_sched_btn = st.form_submit_button("スケジュールの更新", use_container_width=True)

            if update_sched_btn:
              cell = sheet.worksheet("schedules").find(sched_sel_id)
              if cell:
                row_num = cell.row
                sheet.worksheet("schedules").update_cell(row_num, 2, str(e_sched_date))
                sheet.worksheet("schedules").update_cell(row_num, 3, e_sched_content)
                sheet.worksheet("schedules").update_cell(row_num, 4, int(e_sched_capacity))
                st.cache_data.clear()
                time.sleep(0.5)
                st.success("更新しました！")
                time.sleep(1)
                st.rerun()

          # 削除はフォームの外に独立させることで不具合を防ぐ
          if st.button("このスケジュールを削除する", key=f"del_sched_btn_{sched_sel_id}", use_container_width=True):
            cell = sheet.worksheet("schedules").find(sched_sel_id)
            if cell:
              sheet.worksheet("schedules").delete_rows(cell.row)
              st.cache_data.clear()
              time.sleep(0.5)
              st.success("削除しました！")
              time.sleep(1)
              st.rerun()
      else:
        st.write("スケジュールはありません。")

    with tab_memo:
      st.subheader("📝 メモ・不在追加")
      with st.form("add_memo_form"):
        memo_date = st.date_input("日付", value=datetime.today().date(), key="memo_date_input")
        memo_content = st.text_input("内容（例: 不在など）", key="memo_content_input")
        memo_btn = st.form_submit_button("メモを追加", use_container_width=True)

        if memo_btn:
          if memo_content.strip() == "":
            st.warning("内容を入力してください。")
          else:
            memo_id = str(int(time.time()))
            try:
              sheet.worksheet("memos").append_row(
                  [memo_id, str(memo_date), memo_content]
              )
              st.cache_data.clear()
              time.sleep(0.5)
              st.success("メモを追加しました！")
              time.sleep(1)
              st.rerun()
            except Exception as e:
              st.error(f"エラー: {e}")

      st.markdown("---")
      st.subheader("メモ一覧・編集・削除")
      if not df_memos.empty:
        memo_options = {
            f"{row['date']} - {row['content']}": row
            for _, row in df_memos.iterrows()
        }
        selected_memo_key = st.selectbox(
            "編集・削除するメモを選択", list(memo_options.keys()), key="edit_memo_select"
        )

        if selected_memo_key:
          selected_memo_row = memo_options[selected_memo_key]
          memo_sel_id = str(selected_memo_row["id"])

          with st.form(f"edit_memo_form_{memo_sel_id}"):
            try:
              curr_memo_date = datetime.strptime(str(selected_memo_row["date"]), "%Y-%m-%d").date()
            except Exception:
              curr_memo_date = datetime.today().date()

            e_memo_date = st.date_input("日付", value=curr_memo_date, key="e_memo_date")
            e_memo_content = st.text_input("内容", value=str(selected_memo_row["content"]), key="e_memo_content")

            update_memo_btn = st.form_submit_button("メモの更新", use_container_width=True)

            if update_memo_btn:
              cell = sheet.worksheet("memos").find(memo_sel_id)
              if cell:
                row_num = cell.row
                sheet.worksheet("memos").update_cell(row_num, 2, str(e_memo_date))
                sheet.worksheet("memos").update_cell(row_num, 3, e_memo_content)
                st.cache_data.clear()
                time.sleep(0.5)
                st.success("メモを更新しました！")
                time.sleep(1)
                st.rerun()

          if st.button("このメモを削除する", key=f"del_memo_btn_{memo_sel_id}", use_container_width=True):
            cell = sheet.worksheet("memos").find(memo_sel_id)
            if cell:
              sheet.worksheet("memos").delete_rows(cell.row)
              st.cache_data.clear()
              time.sleep(0.5)
              st.success("メモラベルを削除しました！")
              time.sleep(1)
              st.rerun()
      else:
        st.write("登録されたメモはありません。")

    with tab_les:
      st.subheader("🥁 ドラム資料追加")
      with st.form("add_lesson_form"):
        l_title = st.text_input("タイトル")
        l_body = st.text_area("説明文")
        l_images = st.text_area("画像URL（カンマまたは改行区切り）")
        l_video = st.text_input("YouTube動画URL")
        l_status = st.selectbox("ステータス", ["下書き", "公開"])
        l_btn = st.form_submit_button("追加する", use_container_width=True)

        if l_btn:
          formatted_images = ",".join(
              [
                  line.strip()
                  for line in l_images.replace(",", "\n").split("\n")
                  if line.strip()
              ]
          )
          les_id = str(int(time.time()))
          sheet.worksheet("lessons").append_row(
              [les_id, l_title, l_body, formatted_images, l_video, l_status]
          )
          st.cache_data.clear()
          time.sleep(0.5)
          st.success("追加しました！")
          time.sleep(1)
          st.rerun()

      st.markdown("---")
      st.subheader("資料一覧・編集・削除")
      if not df_lessons.empty:
        lesson_options = {
            f"[{row['status']}] {row['title']}": row
            for _, row in df_lessons.iterrows()
        }
        selected_les_key = st.selectbox(
            "編集・削除する資料を選択", list(lesson_options.keys()), key="edit_les_select"
        )

        if selected_les_key:
          selected_les_row = lesson_options[selected_les_key]
          les_sel_id = str(selected_les_row["id"])

          with st.form(f"edit_les_form_{les_sel_id}"):
            e_l_title = st.text_input("タイトル", value=str(selected_les_row["title"]), key="e_l_title")
            e_l_body = st.text_area("説明文", value=str(selected_les_row["body"]), key="e_l_body")
            e_l_images = st.text_area("画像URL（カンマまたは改行区切り）", value=str(selected_les_row["image_urls"]), key="e_l_images")
            e_l_video = st.text_input("YouTube動画URL", value=str(selected_les_row["video_url"]), key="e_l_video")
            
            statuses = ["下書き", "公開"]
            curr_status = str(selected_les_row["status"])
            curr_status_idx = statuses.index(curr_status) if curr_status in statuses else 0
            e_l_status = st.selectbox("ステータス", statuses, index=curr_status_idx, key="e_l_status")

            update_les_btn = st.form_submit_button("資料の更新", use_container_width=True)

            if update_les_btn:
              formatted_images = ",".join(
                  [
                      line.strip()
                      for line in e_l_images.replace(",", "\n").split("\n")
                      if line.strip()
                  ]
              )
              cell = sheet.worksheet("lessons").find(les_sel_id)
              if cell:
                row_num = cell.row
                sheet.worksheet("lessons").update_cell(row_num, 2, e_l_title)
                sheet.worksheet("lessons").update_cell(row_num, 3, e_l_body)
                sheet.worksheet("lessons").update_cell(row_num, 4, formatted_images)
                sheet.worksheet("lessons").update_cell(row_num, 5, e_l_video)
                sheet.worksheet("lessons").update_cell(row_num, 6, e_l_status)
                st.cache_data.clear()
                time.sleep(0.5)
                st.success("資料を更新しました！")
                time.sleep(1)
                st.rerun()

          if st.button("この資料を削除する", key=f"del_les_btn_{les_sel_id}", use_container_width=True):
            cell = sheet.worksheet("lessons").find(les_sel_id)
            if cell:
              sheet.worksheet("lessons").delete_rows(cell.row)
              st.cache_data.clear()
              time.sleep(0.5)
              st.success("資料を削除しました！")
              time.sleep(1)
              st.rerun()
      else:
        st.write("登録された資料はありません。")

    with tab_res_list:
      st.subheader("全予約者データ（一覧）")
      if not df_reservations.empty:
        st.dataframe(df_reservations, use_container_width=True)
        
        st.markdown("---")
        st.subheader("予約の削除・管理")
        res_options = {
            f"📅 {row['date']} - 🎯 {row['content']} - 👤 {row['name']}": row
            for _, row in df_reservations.iterrows()
        }
        selected_res_key = st.selectbox(
            "削除する予約を選択", list(res_options.keys()), key="delete_res_select"
        )

        if selected_res_key:
          selected_res_row = res_options[selected_res_key]
          
          if st.button("選択した予約を削除する", key="admin_del_res_btn", use_container_width=True):
            try:
              cell_list = sheet.worksheet("reservations").findall(str(selected_res_row["name"]))
              target_row = None
              for c in cell_list:
                row_values = sheet.worksheet("reservations").row_values(c.row)
                if (len(row_values) >= 4 and 
                    row_values[1] == str(selected_res_row["date"]) and 
                    row_values[2] == str(selected_res_row["content"]) and 
                    row_values[3] == str(selected_res_row["name"])):
                  target_row = c.row
                  break
              
              if target_row:
                sheet.worksheet("reservations").delete_rows(target_row)
                st.cache_data.clear()
                time.sleep(0.5)
                st.success("予約を削除しました！")
                time.sleep(1)
                st.rerun()
              else:
                st.error("該当する予約データの行が見つかりませんでした。")
            except Exception as e:
              st.error(f"削除処理中にエラーが発生しました: {e}")
      else:
        st.write("まだ予約はありません。")

  elif admin_pass != "":
    st.error("パスワードが違います。")