from datetime import datetime
import time
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st
from streamlit_calendar import calendar

# ページの基本設定
st.set_page_config(
    page_title="自宅イベント予約アプリ", page_icon="🏠", layout="centered"
)

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
  sheet = client.open("自宅イベント予約アプリ")
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
    
    # メモデータの読み込み（memosシートがない場合のフォールバック付き）
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

# サイドバーメニュー
st.sidebar.title("🏠 メニュー")
menu = st.sidebar.radio(
    "ページを選択", ["📅 予約カレンダー", "🥁 ドラム練習ページ", "🔐 管理人ページ"]
)

# ---------------------------------------------------------
# 1. 予約カレンダーページ
# ---------------------------------------------------------
if menu == "📅 予約カレンダー":
  st.title("🏠 自宅イベント予約")
  st.write("カレンダーで空き状況を確認し、下のフォームから予約できます。")

  # カレンダー表示用のイベントリスト作成
  cal_events = []

  # スケジュールイベントの追加
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

    for _, row in df_display.iterrows():
      rem = row["remaining"]
      content_str = str(row["content"])

      if rem <= 0:
        color = "#dc3545"  # 満席：赤
      else:
        if "BBQ" in content_str:
          color = "#e67e22"  # BBQ：オレンジ系
        elif "ドラム" in content_str:
          color = "#2980b9"  # ドラム：青系
        else:
          color = "#8e44ad"  # ダーツ（その他）：紫系

      title_text = f"{content_str}(残{rem})"

      cal_events.append({
          "title": title_text,
          "start": str(row["date"]),
          "allDay": True,
          "backgroundColor": color,
          "borderColor": color,
      })
  else:
    df_display = pd.DataFrame(columns=["id", "date", "content", "capacity", "remaining"])

  # メモ（不在など）イベントの追加（グレー系の色）
  if not df_memos.empty:
    for _, row in df_memos.iterrows():
      cal_events.append({
          "title": str(row["content"]),
          "start": str(row["date"]),
          "allDay": True,
          "backgroundColor": "#7f8c8d",  # メモ：グレー系
          "borderColor": "#7f8c8d",
      })

  # カレンダービューの表示
  calendar_options = {
      "headerToolbar": {
          "left": "prev,next today",
          "center": "title",
          "right": "",
      },
      "initialView": "dayGridMonth",
      "selectable": True,
      "editable": False,
      "height": "450px",
  }

  cal_return = calendar(events=cal_events, options=calendar_options)

  selected_date = None
  if cal_return and "dateClick" in cal_return:
    clicked_date_str = cal_return["dateClick"].get("date")
    if clicked_date_str:
      date_part = clicked_date_str.split("T")[0]
      parsed_date = datetime.strptime(date_part, "%Y-%m-%d").date()
      import datetime as dt
      selected_date = str(parsed_date + dt.timedelta(days=1))

  st.markdown("---")

  if df_schedules.empty:
    st.info("現在、公開されている開催予定はありません。管理人ページから枠を追加してください。")
  else:
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
      st.subheader("🗓️ 予約申し込みフォーム")
    with col_f2:
      date_list = sorted(df_display["date"].unique().tolist())
      default_idx = 0
      if selected_date and selected_date in date_list:
        default_idx = date_list.index(selected_date)
        st.info(f"📅 カレンダーから {selected_date} が選択されました！")

      filter_date = st.selectbox(
          "日付で絞り込み",
          ["すべて表示"] + date_list,
          index=default_idx + 1 if selected_date in date_list else 0,
      )

    if filter_date != "すべて表示":
      filtered_display = df_display[df_display["date"] == filter_date]
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
                    "お名前（ニックネーム可）", key=f"name_{row['id']}_{index}"
                )
                submit = st.form_submit_button("予約する")
                if submit:
                  if user_name.strip() == "":
                    st.warning("お名前を入力してください。")
                  else:
                    new_row = [
                        str(row["id"]),
                        str(row["date"]),
                        str(row["content"]),
                        str(user_name),
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
# 2. ドラム練習ページ
# ---------------------------------------------------------
elif menu == "🥁 ドラム練習ページ":
  st.title("🥁 ドラム練習・楽譜置き場")
  st.write("管理人が準備したドラムの楽譜やレッスン動画を確認できます。")

  if df_lessons.empty:
    st.info("まだ公開されているレッスン記事はありません。")
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
          st.markdown("### 📺 レッスン動画")
          st.video(lesson["video_url"])

        if lesson["image_urls"]:
          st.markdown("### 🖼️ 楽譜・資料画像")
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
# 3. 管理人ページ
# ---------------------------------------------------------
elif menu == "🔐 管理人ページ":
  st.title("🔐 管理人専用ダッシュボード")

  admin_pass = st.text_input("管理人パスワードを入力", type="password")
  if admin_pass == "admin123":
    st.success("認証成功しました！")

    tab_sch, tab_memo, tab_les, tab_res_list = st.tabs(
        ["🗓️ 枠の管理", "📝 メモ・不在の管理", "🥁 ドラム資料の管理", "📋 予約者一覧"]
    )

    with tab_sch:
      st.subheader("🗓️ 開催スケジュール確認・追加カレンダー")
      st.write("カレンダーの日付をクリックすると、その日の枠を簡単に追加できます！")

      if "admin_selected_date" not in st.session_state:
        st.session_state.admin_selected_date = None

      admin_cal_events = []
      if not df_schedules.empty:
        if not df_reservations.empty:
          res_counts_adm = (
              df_reservations.groupby(["date", "content"])
              .size()
              .reset_index(name="booked_count")
          )
          df_adm_display = pd.merge(
              df_schedules, res_counts_adm, on=["date", "content"], how="left"
          )
          df_adm_display["booked_count"] = (
              df_adm_display["booked_count"].fillna(0).astype(int)
          )
        else:
          df_adm_display = df_schedules.copy()
          df_adm_display["booked_count"] = 0

        df_adm_display["remaining"] = (
            df_adm_display["capacity"] - df_adm_display["booked_count"]
        )

        for _, row in df_adm_display.iterrows():
          content_str = str(row['content'])
          rem = row["remaining"]

          if rem <= 0:
            adm_color = "#dc3545"
          else:
            if "BBQ" in content_str:
              adm_color = "#e67e22"
            elif "ドラム" in content_str:
              adm_color = "#2980b9"
            else:
              adm_color = "#8e44ad"

          admin_cal_events.append({
              "title": f"{content_str}(残{rem})",
              "start": str(row["date"]),
              "allDay": True,
              "backgroundColor": adm_color,
              "borderColor": adm_color,
          })

      # 管理人カレンダーにもメモを表示
      if not df_memos.empty:
        for _, row in df_memos.iterrows():
          admin_cal_events.append({
              "title": str(row["content"]),
              "start": str(row["date"]),
              "allDay": True,
              "backgroundColor": "#7f8c8d",
              "borderColor": "#7f8c8d",
          })

      admin_calendar_options = {
          "headerToolbar": {
              "left": "prev,next today",
              "center": "title",
              "right": "",
          },
          "initialView": "dayGridMonth",
          "selectable": True,
          "editable": False,
          "height": "420px",
      }
      admin_cal_return = calendar(
          events=admin_cal_events,
          options=admin_calendar_options,
          key="admin_calendar",
      )

      if admin_cal_return and "dateClick" in admin_cal_return:
        clicked_date_str = admin_cal_return["dateClick"].get("date")
        if clicked_date_str:
          date_part = clicked_date_str.split("T")[0]
          parsed_date = datetime.strptime(date_part, "%Y-%m-%d").date()
          
          import datetime as dt
          st.session_state.admin_selected_date = parsed_date + dt.timedelta(days=1)

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

      default_date = (
          st.session_state.admin_selected_date
          if st.session_state.admin_selected_date
          else datetime.today().date()
      )

      new_date = st.date_input("開催日", value=default_date)
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

        # IDを表示しないように変更
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

        # IDを表示しないように変更
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
        # IDを表示しないように変更
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
            e_title = st.text_input("タイトル", value=str(selected_row["title"]))
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
              delete_btn = st.form_submit_button("このレッスンを削除する")

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