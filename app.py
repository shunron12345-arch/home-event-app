from datetime import datetime
import time
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

# ページの基本設定（スマホで見やすいように設定）
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
    # JSONとしてそのまま読み込めるように辞書化
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
        else pd.DataFrame(columns=["id", "title", "body", "video_url", "status"])
    )
    return df_schedules, df_reservations, df_lessons
  except Exception as e:
    st.error(f"データの読み込み中にエラーが発生しました: {e}")
    return (
        pd.DataFrame(columns=["id", "date", "content", "capacity"]),
        pd.DataFrame(columns=["id", "date", "content", "name"]),
        pd.DataFrame(columns=["id", "title", "body", "video_url", "status"]),
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
  st.write("URLを知っている人専用の予約ページです！参加したい枠を選んでね。")

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

    st.subheader("🗓️ 開催スケジュール一覧")

    for index, row in df_display.iterrows():
      with st.container():
        st.markdown(f"---")
        col1, col2 = st.columns([2, 1])
        with col1:
          st.markdown(f"**📅 日付:** {row['date']}")
          st.markdown(f"**🎯 イベント:** {row['content']}")
          rem = row["remaining"]
          cap = row["capacity"]
          if rem > 0:
            st.markdown(
                f"**🟢 残り枠:** <span style='color:green; font-weight:bold;'>{rem}"
                f"名</span> (定員: {cap}名)",
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
                  # スプレッドシートに書き込み
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

# ---------------------------------------------------------
# 2. ドラム練習ページ
# ---------------------------------------------------------
elif menu == "🥁 ドラム練習ページ":
  st.title("🥁 ドラム練習・楽譜置き場")
  st.write("管理人が準備したドラムの楽譜やレッスン動画を確認できます。")

  if df_lessons.empty:
    st.info("まだ公開されているレッスン記事はありません。")
  else:
    published_lessons = df_lessons[df_lessons["status"] == "公開"]
    if published_lessons.empty:
      st.info("現在準備中のため、公開されている記事はありません。")
    else:
      for _, lesson in published_lessons.iterrows():
        st.markdown(f"### {lesson['title']}")
        st.markdown(f"{lesson['body']}")
        if lesson["video_url"]:
          st.video(lesson["video_url"])
        st.markdown("---")

# ---------------------------------------------------------
# 3. 管理人ページ
# ---------------------------------------------------------
elif menu == "🔐 管理人ページ":
  st.title("🔐 管理人専用ダッシュボード")

  # パスワード認証
  admin_pass = st.text_input("管理人パスワードを入力", type="password")
  # 簡易パスワード（必要に応じて変更してください）
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
        # 削除機能
        del_id = st.text_input("削除したい枠のIDを入力")
        if st.button("指定したIDの枠を削除"):
          # 行削除の処理
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
        l_video = st.text_input("YouTube動画URL（任意）")
        l_status = st.selectbox("ステータス", ["下書き", "公開"])
        l_btn = st.form_submit_button("レッスン資料を追加")

        if l_btn:
          les_id = str(int(time.time()))
          sheet.worksheet("lessons").append_row(
              [les_id, l_title, l_body, l_video, l_status]
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