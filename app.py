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


# データの読み込み関数
def load_data():
  try:
    schedules_data = sheet.worksheet("schedules").get_all_records()
    reservations_data = sheet.worksheet("reservations").get_all_records()
    lessons_data = sheet.worksheet("lessons").get_all_records()

    df_schedules = (
        pd.DataFrame(schedules_data)
        if schedules_data
        else pd.DataFrame(columns=["id", "date", "content", "capacity"])
    )
    df_reservations = (
        pd.DataFrame(reservations_data)
        if reservations_data
        else pd.DataFrame(columns=["id", "date", "content", "name"])
    )
    df_lessons = (
        pd.DataFrame(lessons_data)
        if lessons_data
        else pd.DataFrame(
            columns=["id", "title", "body", "image_urls", "video_url", "status"]
        )
    )
    return df_schedules, df_reservations, df_lessons
  except Exception as e:
    st.error(f"データの読み込み中にエラーが発生しました: {e}")
    return (
        pd.DataFrame(columns=["id", "date", "content", "capacity"]),
        pd.DataFrame(columns=["id", "date", "content", "name"]),
        pd.DataFrame(
            columns=["id", "title", "body", "image_urls", "video_url", "status"]
        ),
    )


df_schedules, df_reservations, df_lessons = load_data()

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

  if df_schedules.empty:
    st.info(
        "現在、公開されている開催予定はありません。管理人が枠を追加するまでお待ち"
        "ください。"
    )
  else:
    # 予約人数の計算
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

    # ------------------
    # カレンダービューの作成
    # ------------------
    cal_events = []
    for _, row in df_display.iterrows():
      rem = row["remaining"]
      status_text = f"残り{rem}枠" if rem > 0 else "満席"
      color = "#28a745" if rem > 0 else "#dc3545"  # 空きは緑、満席は赤

      # アイコンを付与
      icon = "🍖" if "BBQ" in str(row["content"]) else ("🥁" if "ドラム" in str(row["content"]) else "🎯")

      cal_events.append({
          "title": f"{icon} {row['content']} ({status_text})",
          "start": str(row["date"]),
          "allDay": True,
          "backgroundColor": color,
          "borderColor": color,
      })

    calendar_options = {
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek",
        },
        "initialView": "dayGridMonth",
        "selectable": True,
        "editable": False,
        "height": "450px",
    }

    # カレンダーの表示とクリックイベントの取得
    cal_return = calendar(events=cal_events, options=calendar_options)

    # カレンダー上で日付が選択された場合、その日付のデータを優先して絞り込む機能
    selected_date = None
    if cal_return and "dateClick" in cal_return:
      selected_date = cal_return["dateClick"].get("date")

    st.markdown("---")

    # 絞り込みフィルター
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
      st.subheader("🗓️ 予約申し込みフォーム")
    with col_f2:
      # 日付で絞り込むセレクトボックス
      date_list = sorted(df_display["date"].unique().tolist())
      
      # カレンダーでクリックされた日付があれば、それを初期選択にする
      default_idx = 0
      if selected_date and selected_date in date_list:
        default_idx = date_list.index(selected_date)
        st.info(f"📅 カレンダーから {selected_date} が選択されました！")

      filter_date = st.selectbox("日付で絞り込み", ["すべて表示"] + date_list, index=default_idx + 1 if selected_date in date_list else 0)

    # 表示データの絞り込み
    if filter_date != "すべて表示":
      filtered_display = df_display[df_display["date"] == filter_date]
    else:
      filtered_display = df_display

    if filtered_display.empty:
      st.info("選択された日付の開催枠はありません。")
    else:
      for index, row in filtered_display.iterrows():
        with st.container():
          col1, col2 = st.columns([2, 1])
          with col1:
            st.markdown(f"**📅 日付:** {row['date']}")
            st.markdown(f"**🎯 イベント:** {row['content']}")
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

          with col2:
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

    tab_sch, tab_les, tab_res_list = st.tabs(
        ["🗓️ 枠の管理", "🥁 ドラム資料の管理", "📋 予約者一覧"]
    )

    with tab_sch:
      st.subheader("新しい開催枠の追加")
      with st.form("add_schedule_form"):
        new_date = st.date_input("開催日")
        new_content = st.selectbox(
            "コンテンツ", ["①BBQ", "②ドラム", "③ダーツ"]
        )
        new_capacity = st.number_input("定員数", min_value=1, value=5)
        add_btn = st.form_submit_button("枠を追加する")

        if add_btn:
          sched_id = str(int(time.time()))
          sheet.worksheet("schedules").append_row(
              [sched_id, str(new_date), new_content, int(new_capacity)]
          )
          st.success("新しい枠を追加しました！")
          time.sleep(1)
          st.rerun()

      st.subheader("登録済みのスケジュール一覧")
      if not df_schedules.empty:
        st.dataframe(df_schedules)
        del_id = st.text_input("削除したい枠のIDを入力")
        if st.button("指定したIDの枠を削除"):
          cell = sheet.worksheet("schedules").find(str(del_id))
          if cell:
            sheet.worksheet("schedules").delete_rows(cell.row)
            st.success("削除しました！")
            time.sleep(1)
            st.rerun()
          else:
            st.error("指定したIDが見つかりませんでした。")
      else:
        st.write("登録されているスケジュールはありません。")

    with tab_les:
      st.subheader("ドラム資料（楽譜・動画）の追加・編集")
      with st.form("add_lesson_form"):
        l_title = st.text_input("タイトル（例: 初心者向け基本ビート）")
        l_body = st.text_area("説明文・楽譜メモなど")
        l_images = st.text_area(
            "画像URL（複数ある場合は改行またはカンマ区切りで入力）"
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
          st.success("レッスン資料を保存しました！")
          time.sleep(1)
          st.rerun()

      st.subheader("現在のレッスン一覧")
      if not df_lessons.empty:
        st.dataframe(df_lessons)
      else:
        st.write("レッスン資料はありません。")

    with tab_res_list:
      st.subheader("現在の全予約者データ")
      if not df_reservations.empty:
        st.dataframe(df_reservations)
      else:
        st.write("まだ誰も予約していません。")

  elif admin_pass != "":
    st.error("パスワードが違います。")