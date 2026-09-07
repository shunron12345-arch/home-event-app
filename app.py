import calendar
from datetime import datetime, date
import time
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# ページの基本設定
st.set_page_config(
    page_title="予約アプリ", page_icon="🏠", layout="centered"
)

# 曜日リストの定義（共通）
weekdays = ["月", "火", "水", "木", "金", "土", "日"]

# Googleスプレッドシート接続設定
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
  st.error(
      f"スプレッドシートへの接続に失敗しました。認証設定を確認してください: {e}"
  )
  st.stop()


# データの読み込み関数（API制限対策としてキャッシュを追加）
@st.cache_data(ttl=30)
def load_data():
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
        pd.DataFrame(
            columns=["id", "title", "body", "image_urls", "video_url", "status"]
        ),
        pd.DataFrame(columns=["id", "date", "content"]),
    )


df_schedules, df_reservations, df_lessons, df_memos = load_data()


# ユーザのセッション状態の初期化（自分の名前をブラウザごとに記憶）
if "my_name" not in st.session_state:
  st.session_state.my_name = ""


# サイドバーメニュー
st.sidebar.title("🏠 メニュー")
menu = st.sidebar.radio(
    "ページを選択", ["📅 予約カレンダー", "👤 自分の予約・変更", "🥁 ドラム練習用", "🔐 管理人ページ"]
)

# ---------------------------------------------------------
# 1. 予約カレンダーページ
# ---------------------------------------------------------
if menu == "📅 予約カレンダー":
  st.title("予約")
  st.write("カレンダーの日付をクリックすると、下の予約申し込みフォームがその日付に絞り込まれます。")

  # スマホ対応：ボタンが縦方向に自由に拡大・折り返しできるようにCSSを調整
  st.markdown("""
    <style>
    /* 7列グリッドの維持 */
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
    /* ボタンの共通ポップデザイン */
    div[data-testid="stButton"] button {
        border-radius: 8px;
        border: 2px solid #e2e8f0;
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        color: #1e293b;
        font-weight: 700;
        padding: 6px 12px !important;
        font-size: 0.65rem !important;
        line-height: 1.2 !important;
        white-space: pre-line !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }
    /* カレンダー内の日付ボタン（縦方向に自由に拡大・テキスト折り返し対応） */
    div[data-testid="stColumn"] div[data-testid="stButton"] button {
        width: 100% !important;
        height: auto !important;
        min-height: 50px !important;
        padding: 4px 1px !important;
        font-size: 0.55rem !important;
        white-space: pre-line !important;
    }
    /* 月切り替えボタンのコンパクト化 */
    div.row-widget.stButton > button {
        width: 100% !important;
    }
    div[data-testid="stButton"] button:hover {
        border-color: #ec4899;
        color: #ec4899;
        background: linear-gradient(135deg, #fdf2f8 0%, #fce7f3 100%);
        transform: translateY(-1px);
    }
    </style>
    """, unsafe_allow_html=True)

  # データの集計処理
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

    # 過去の日付のイベントを自動的に除外する処理
    today_str = datetime.today().strftime("%Y-%m-%d")
    df_display = df_display[df_display["date"] >= today_str]

    # 同一日付に「1人以上予約されたイベント」がある場合、ほかの「予約0のイベント」を非表示にする処理
    if not df_display.empty:
      dates_with_bookings = df_display[df_display["booked_count"] > 0]["date"].unique()
      df_display = df_display[
          (~df_display["date"].isin(dates_with_bookings)) | (df_display["booked_count"] > 0)
      ]
  else:
    df_display = pd.DataFrame(columns=["id", "date", "content", "capacity", "remaining"])

  # セッションステートの初期化
  if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.today().year
  if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.today().month
  if "selected_date" not in st.session_state:
    st.session_state.selected_date = "すべて表示"

  # 月切り替えコントロール
  col_title, col_prev, col_next = st.columns([2, 1.2, 1.2])
  with col_title:
    st.markdown(
        f"<h3 style='margin: 0; font-size: 1.2rem; padding-top: 8px; color: #000000; font-weight: bold;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</h3>",
        unsafe_allow_html=True,
    )
  with col_prev:
    if st.button("◀ 前月", use_container_width=True):
      if st.session_state.cal_month == 1:
        st.session_state.cal_month = 12
        st.session_state.cal_year -= 1
      else:
        st.session_state.cal_month -= 1
      st.rerun()
  with col_next:
    if st.button("次月 ▶", use_container_width=True):
      if st.session_state.cal_month == 12:
        st.session_state.cal_month = 1
        st.session_state.cal_year += 1
      else:
        st.session_state.cal_month += 1
      st.rerun()

  st.markdown("<br>", unsafe_allow_html=True)

  # ネイティブカレンダー（グリッド表示）の描画
  cols = st.columns(7)
  for i, day_name in enumerate(weekdays):
    cols[i].markdown(f"<div style='text-align: center; font-weight: bold; color: #db2777; font-size: 0.8rem;'>{day_name}</div>", unsafe_allow_html=True)

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

          if st.session_state.selected_date == date_str:
            btn_label = f"⭐{day}\n"
          else:
            btn_label = f"{day}\n"

          if not day_schedules.empty:
            content_lines = []
            for _, sched in day_schedules.iterrows():
              c_name = str(sched["content"])
              if "BBQ" in c_name:
                emoji = "🍖"
              elif "ドラム" in c_name:
                emoji = "🥁"
              elif "ダーツ" in c_name:
                emoji = "🎯"
              else:
                emoji = "📌"
              
              rem = sched["remaining"]
              content_lines.append(f"{emoji}{rem}")
            
            btn_label += "\n".join(content_lines)
          elif has_memo:
            btn_label += "📝"

          if st.button(btn_label, key=f"cal_day_{date_str}", use_container_width=True):
            st.session_state.selected_date = date_str
            st.rerun()

  if st.button("すべての期間を表示する", use_container_width=True):
    st.session_state.selected_date = "すべて表示"
    st.rerun()

  st.markdown("---")

  # 予約申し込みフォーム
  if df_schedules.empty or df_display.empty:
    st.info("現在、公開されている開催予定はありません。管理人ページから枠を追加してください。")
  else:
    st.subheader("🗓️ 予約申し込みフォーム（一覧）")
    date_list = sorted(df_display["date"].unique().tolist())
    
    filter_options = ["すべて表示"] + date_list
    
    current_index = 0
    if st.session_state.selected_date in filter_options:
      current_index = filter_options.index(st.session_state.selected_date)

    filter_date = st.selectbox(
        "日付で絞り込み",
        filter_options,
        index=current_index,
        key="selectbox_filter_date"
    )

    if filter_date != st.session_state.selected_date:
      st.session_state.selected_date = filter_date

    if st.session_state.selected_date != "すべて表示":
      filtered_display = df_display[df_display["date"] == st.session_state.selected_date]
    else:
      filtered_display = df_display

    if filtered_display.empty:
      st.info("選択された日付の開催枠はありません。")
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

          col1, col2, col3 = st.columns([1, 2, 1.5])
          with col1:
            try:
              st.image(img_path, use_container_width=True)
            except Exception:
              st.write("🖼️ 画像なし")

          with col2:
            st.markdown(f"**📅 日付:** {row['date']}")
            st.markdown(f"**🎯 イベント:** {content_str}")
            rem = row["remaining"]
            cap = row["capacity"]
            if rem > 0:
              st.markdown(
                  f"**🟢 残り枠:** <span style='color:green; font-weight:bold;'>{rem}"
                  f"枠</span> (定員: {cap}名)",
                  unsafe_allow_html=True,
              )
            else:
              st.markdown(
                  f"**🔴 残り枠:** <span"
                  " style='color:red; font-weight:bold;'>満席</span>"
                  f" (定員: {cap}名)",
                  unsafe_allow_html=True,
              )

          with col3:
            if rem > 0:
              with st.form(key=f"予約form_{row['id']}_{index}"):
                user_name = st.text_input(
                    "お名前", value=st.session_state.my_name, key=f"name_{row['id']}_{index}"
                )
                submit = st.form_submit_button("予約する")
                if submit:
                  if user_name.strip() == "":
                    st.warning("お名前を入力してください。")
                  else:
                    st.session_state.my_name = user_name.strip()
                    new_row = [
                        str(row["id"]),
                        str(row["date"]),
                        str(row["content"]),
                        str(user_name.strip()),
                    ]
                    sheet.worksheet("reservations").append_row(new_row)
                    st.cache_data.clear()
                    st.success(
                        f"{row['date']}の【{row['content']}】を予約しました！"
                    )
                    time.sleep(1)
                    st.rerun()
            else:
              st.write("❌ 満席です")
          st.markdown(f"---")

# ---------------------------------------------------------
# 2. 自分の予約・変更ページ
# ---------------------------------------------------------
elif menu == "👤 自分の予約・変更":
  st.title("👤 自分の予約一覧・キャンセル")
  st.write("このブラウザで予約した際に入力したお名前をもとに、ご自身の予約を確認・キャンセルできます。")

  input_name = st.text_input("お名前を入力して確認", value=st.session_state.my_name)
  
  if input_name:
    st.session_state.my_name = input_name.strip()
    
    if df_reservations.empty:
      st.info("現在、登録されている予約はありません。")
    else:
      my_res = df_reservations[df_reservations["name"] == st.session_state.my_name]
      
      if my_res.empty:
        st.info(f"「{st.session_state.my_name}」様名義の予約は見つかりませんでした。")
      else:
        st.success(f"「{st.session_state.my_name}」様の予約が見つかりました（全 {len(my_res)} 件）")
        
        for idx, res in my_res.iterrows():
          with st.container():
            st.markdown(f"**📅 日付:** {res['date']}")
            st.markdown(f"**🎯 イベント:** {res['content']}")
            
            if st.button("この予約をキャンセル（取り消し）する", key=f"cancel_{res['date']}_{res['content']}_{idx}"):
              try:
                # スプレッドシートから該当する行を検索して削除
                cell = sheet.worksheet("reservations").find(str(res["name"]))
                # 日付とコンテンツ、名前が一致する行を探す
                cell_list = sheet.worksheet("reservations").findall(str(res["name"]))
                target_row = None
                for c in cell_list:
                  row_values = sheet.worksheet("reservations").row_values(c.row)
                  # row_values: [id, date, content, name]
                  if len(row_values) >= 4 and row_values[1] == str(res["date"]) and row_values[2] == str(res["content"]) and row_values[3] == str(res["name"]):
                    target_row = c.row
                    break
                
                if target_row:
                  sheet.worksheet("reservations").delete_rows(target_row)
                  st.cache_data.clear()
                  st.success("予約をキャンセルしました。")
                  time.sleep(1)
                  st.rerun()
                else:
                  st.error("該当する予約データの行が見つかりませんでした。")
              except Exception as e:
                st.error(f"キャンセル処理中にエラーが発生しました: {e}")
            st.markdown("---")
  else:
    st.info("お名前を入力すると、該当する予約が表示されます。")

# ---------------------------------------------------------
# 3. ドラム練習用
# ---------------------------------------------------------
elif menu == "🥁 ドラム練習用":
  st.title("🥁 楽譜等の置き場")
  st.write("管理人が準備したドラムの楽譜やレッスン動画を確認できます。")

  if df_lessons.empty:
    st.info("まだ公開されている記事はありません。")
  else:
    if "image_urls" not in df_lessons.columns:
      df_lessons["image_urls"] = ""

    published_lessons = df_lessons[df_lessons["status"] == "公開"]
    if published_lessons.empty:
      st.info("現在準備中のため、公開されている記事はありません。")
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
  st.title("🔐 管理人専用ダッシュボード")

  admin_pass = st.text_input("管理人パスワードを入力", type="password")
  if admin_pass == "admin123":
    st.success("認証成功しました！")

    tab_sch, tab_memo, tab_les, tab_res_list = st.tabs(
        ["🗓️ 枠の管理", "📝 メモの管理", "🥁 ドラム資料の管理", "📋 予約者一覧"]
    )

    with tab_sch:
      st.subheader("🗓️ 開催スケジュール確認・追加カレンダー")
      st.write("カレンダーの日付ボタンを押すと、下の開催日として自動選択されます。")

      if "admin_selected_date" not in st.session_state:
        st.session_state.admin_selected_date = datetime.today().date()

      col_atitle, col_aprev, col_anext = st.columns([2, 1.2, 1.2])
      with col_atitle:
        st.markdown(
            f"<h3 style='margin: 0; font-size: 1.2rem; padding-top: 8px; color: #000000; font-weight: bold;'>{st.session_state.cal_year}年 {st.session_state.cal_month}月</h3>",
            unsafe_allow_html=True,
        )
      with col_aprev:
        if st.button("◀ 前月", key="adm_prev", use_container_width=True):
          if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
          else:
            st.session_state.cal_month -= 1
          st.rerun()
      with col_anext:
        if st.button("次月 ▶", key="adm_next", use_container_width=True):
          if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1
            st.session_state.cal_year += 1
          else:
            st.session_state.cal_month += 1
          st.rerun()

      st.markdown("<br>", unsafe_allow_html=True)

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
              if st.button(f"{day}", key=f"adm_day_{date_str}", use_container_width=True):
                st.session_state.admin_selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                st.rerun()

      st.markdown("---")
      st.subheader("新しい開催枠の追加")

      if "content_select" not in st.session_state:
        st.session_state.content_select = "BBQ"
      if "capacity_input" not in st.session_state:
        st.session_state.capacity_input = 4

      def on_content_change():
        content = st.session_state.content_select
        if "BBQ" in content:
          st.session_state.capacity_input = 4
        elif "ドラム" in content:
          st.session_state.capacity_input = 1
        elif "ダーツ" in content:
          st.session_state.capacity_input = 6

      new_date = st.date_input("開催日", value=st.session_state.admin_selected_date)
      new_content = st.selectbox(
          "コンテンツ",
          ["BBQ", "ドラム", "ダーツ"],
          key="content_select",
          on_change=on_content_change
      )
      new_capacity = st.number_input(
          "定員数",
          min_value=1,
          key="capacity_input"
      )

      if st.button("枠を追加する"):
        sched_id = str(int(time.time()))
        sheet.worksheet("schedules").append_row(
            [sched_id, str(new_date), new_content, int(new_capacity)]
        )
        st.cache_data.clear()
        st.success(f"{new_date} に新しい枠を追加しました！")
        time.sleep(1)
        st.rerun()

      st.markdown("---")
      st.subheader("登録済みのスケジュール一覧・編集・削除")
      if not df_schedules.empty:
        st.dataframe(df_schedules, use_container_width=True)

        schedule_options = {
            f"{row['date']} - {row['content']} (定員: {row['capacity']})": row
            for _, row in df_schedules.iterrows()
        }
        selected_sched_key = st.selectbox(
            "編集・削除するスケジュールを選択", list(schedule_options.keys()), key="edit_sched_select"
        )

        if selected_sched_key:
          selected_sched_row = schedule_options[selected_sched_key]
          sched_sel_id = str(selected_sched_row["id"])

          with st.form(f"edit_sched_form_{sched_sel_id}"):
            try:
              curr_date = datetime.strptime(str(selected_sched_row["date"]), "%Y-%m-%d").date()
            except Exception:
              curr_date = datetime.today().date()

            e_sched_date = st.date_input("開催日", value=curr_date)
            
            contents = ["BBQ", "ドラム", "ダーツ"]
            curr_content = str(selected_sched_row["content"])
            curr_content_idx = contents.index(curr_content) if curr_content in contents else 0
            e_sched_content = st.selectbox("コンテンツ", contents, index=curr_content_idx)
            
            try:
              curr_cap = int(selected_sched_row["capacity"])
            except Exception:
              curr_cap = 4
            e_sched_capacity = st.number_input("定員数", min_value=1, value=curr_cap)

            col_su1, col_su2 = st.columns(2)
            with col_su1:
              update_sched_btn = st.form_submit_button("スケジュールの更新")
            with col_su2:
              delete_sched_btn = st.form_submit_button("このスケジュールを削除")

            if update_sched_btn:
              cell = sheet.worksheet("schedules").find(sched_sel_id)
              if cell:
                row_num = cell.row
                sheet.worksheet("schedules").update_cell(row_num, 2, str(e_sched_date))
                sheet.worksheet("schedules").update_cell(row_num, 3, e_sched_content)
                sheet.worksheet("schedules").update_cell(row_num, 4, int(e_sched_capacity))
                st.cache_data.clear()
                st.success("スケジュールを更新しました！")
                time.sleep(1)
                st.rerun()
              else:
                st.error("該当するスケジュールIDが見つかりませんでした。")

            if delete_sched_btn:
              cell = sheet.worksheet("schedules").find(sched_sel_id)
              if cell:
                sheet.worksheet("schedules").delete_rows(cell.row)
                st.cache_data.clear()
                st.success("スケジュールを削除しました！")
                time.sleep(1)
                st.rerun()
              else:
                st.error("該当するスケジュールIDが見つかりませんでした。")
      else:
        st.write("登録されているスケジュールはありません。")

    with tab_memo:
      st.subheader("📝 メモ・不在予定の追加")
      with st.form("add_memo_form"):
        memo_date = st.date_input("日付", value=datetime.today().date(), key="memo_date_input")
        memo_content = st.text_input("内容（例: 不在、終日外出、旅行など）", key="memo_content_input")
        memo_btn = st.form_submit_button("メモを追加する")

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
              st.success(f"{memo_date} にメモを追加しました！")
              time.sleep(1)
              st.rerun()
            except Exception as e:
              st.error(f"スプレッドシートへの保存に失敗しました。'memos' シートが存在するか確認してください: {e}")

      st.markdown("---")
      st.subheader("登録済みのメモ一覧・編集・削除")
      if not df_memos.empty:
        st.dataframe(df_memos, use_container_width=True)

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

            e_memo_date = st.date_input("日付", value=curr_memo_date, key=f"e_date_{memo_sel_id}")
            e_memo_content = st.text_input("内容", value=str(selected_memo_row["content"]), key=f"e_content_{memo_sel_id}")

            col_mu1, col_mu2 = st.columns(2)
            with col_mu1:
              update_memo_btn = st.form_submit_button("メモの更新")
            with col_mu2:
              delete_memo_btn = st.form_submit_button("このメモを削除")

            if update_memo_btn:
              cell = sheet.worksheet("memos").find(memo_sel_id)
              if cell:
                row_num = cell.row
                sheet.worksheet("memos").update_cell(row_num, 2, str(e_memo_date))
                sheet.worksheet("memos").update_cell(row_num, 3, e_memo_content)
                st.cache_data.clear()
                st.success("メモを更新しました！")
                time.sleep(1)
                st.rerun()
              else:
                st.error("該当するメモIDが見つかりませんでした。")

            if delete_memo_btn:
              cell = sheet.worksheet("memos").find(memo_sel_id)
              if cell:
                sheet.worksheet("memos").delete_rows(cell.row)
                st.cache_data.clear()
                st.success("メモを削除しました！")
                time.sleep(1)
                st.rerun()
              else:
                st.error("該当するメモIDが見つかりませんでした。")
      else:
        st.write("登録されているメモはありません。")

    with tab_les:
      st.subheader("ドラム資料（楽譜・動画）の追加")
      with st.form("add_lesson_form"):
        l_title = st.text_input("タイトル（例: 初心者向け基本ビート）")
        l_body = st.text_area("説明文・楽譜メモなど")
        l_images = st.text_area(
            "画像パス・URL（複数ある場合は改行またはカンマ区切りで入力）"
        )
        l_video = st.text_input("YouTube動画URL（限定公開URLなど）")
        l_status = st.selectbox("ステータス", ["下書き", "公開"])
        l_btn = st.form_submit_button("レッスン資料を追加")

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
          st.success("レッスン資料を保存しました！")
          time.sleep(1)
          st.rerun()

      st.markdown("---")
      st.subheader("レッスン資料の編集・削除")
      if not df_lessons.empty:
        lesson_options = {
            f"{row['title']}": row
            for _, row in df_lessons.iterrows()
        }
        selected_lesson_key = st.selectbox(
            "編集・削除するレッスンを選択", list(lesson_options.keys())
        )

        if selected_lesson_key:
          selected_row = lesson_options[selected_lesson_key]
          sel_id = str(selected_row["id"])

          with st.form(f"edit_lesson_form_{sel_id}"):
            e_title = st.text_input("Title", value=str(selected_row["title"]))
            e_body = st.text_area("説明文・楽譜メモなど", value=str(selected_row["body"]))
            e_images = st.text_area(
                "画像パス・URL（改行またはカンマ区切り）",
                value=str(selected_row["image_urls"]),
            )
            e_video = st.text_input("YouTube動画URL", value=str(selected_row["video_url"]))

            current_status = str(selected_row["status"])
            status_options = ["下書き", "公開"]
            default_status_idx = (
                status_options.index(current_status)
                if current_status in status_options
                else 0
            )
            e_status = st.selectbox(
                "ステータス", status_options, index=default_status_idx
            )

            col_u1, col_u2 = st.columns(2)
            with col_u1:
              update_btn = st.form_submit_button("更新する")
            with col_u2:
              delete_btn = st.form_submit_button("このレッスン資料を削除する")

            if update_btn:
              formatted_images = ",".join(
                  [
                      line.strip()
                      for line in e_images.replace(",", "\n").split("\n")
                      if line.strip()
                  ]
              )
              cell = sheet.worksheet("lessons").find(sel_id)
              if cell:
                row_num = cell.row
                sheet.worksheet("lessons").update_cell(row_num, 2, e_title)
                sheet.worksheet("lessons").update_cell(row_num, 3, e_body)
                sheet.worksheet("lessons").update_cell(row_num, 4, formatted_images)
                sheet.worksheet("lessons").update_cell(row_num, 5, e_video)
                sheet.worksheet("lessons").update_cell(row_num, 6, e_status)
                st.cache_data.clear()
                st.success("レッスン資料を更新しました！")
                time.sleep(1)
                st.rerun()
              else:
                st.error("該当するレッスンIDが見つかりませんでした。")

            if delete_btn:
              cell = sheet.worksheet("lessons").find(sel_id)
              if cell:
                sheet.worksheet("lessons").delete_rows(cell.row)
                st.cache_data.clear()
                st.success("レッスン資料を削除しました！")
                time.sleep(1)
                st.rerun()
              else:
                st.error("該当するレッスンIDが見つかりませんでした。")
      else:
        st.write("編集できるレッスン資料はありません。")

    with tab_res_list:
      st.subheader("現在の全予約者データ")
      if not df_reservations.empty:
        st.dataframe(df_reservations)
      else:
        st.write("まだ誰も予約していません。")

  elif admin_pass != "":
    st.error("パスワードが違います。")