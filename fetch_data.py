import csv
import datetime
import io
import json
import ssl
import sys
import urllib.error
import urllib.request


def fetch_url(url, headers):
  """SSLチェックを回避しつつ指定URLからバイナリを取得する"""
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
    return res.read()


def main():
  print("==========================================")
  print(" WBGT & アメダスデータ取得処理を開始します ")
  print("==========================================")

  # 環境省・気象庁共通ヘッダー
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      ),
      "Accept": (
          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webkit,*/*;q=0.8"
      ),
      "Accept-Language": "ja-JP,ja;q=0.9",
  }

  # ---------------------------------------------------------
  # 1. 環境省公式WBGTデータの取得
  # ---------------------------------------------------------
  print("[1/3] 環境省の公式WBGTデータをダウンロード中...")
  moe_by_id = {}
  moe_by_name = {}

  # 環境省の最新データ配信URLパターン
  moe_urls = [
      "https://www.wbgt.env.go.jp/prev15d/dl/wbgt_all_latest.csv",
      "https://www.wbgt.env.go.jp/est15d/dl/wbgt_all_latest.csv",
      "https://www.wbgt.env.go.jp/day/dl/wbgt_all_latest.csv",
  ]

  moe_success = False
  for url in moe_urls:
    try:
      # 環境省用にRefererを付与
      env_headers = headers.copy()
      env_headers["Referer"] = "https://www.wbgt.env.go.jp/"

      raw_bytes = fetch_url(url, env_headers)
      try:
        csv_text = raw_bytes.decode("cp932")
      except Exception:
        csv_text = raw_bytes.decode("utf-8", errors="ignore")

      f = io.StringIO(csv_text)
      reader = csv.reader(f)
      rows = list(reader)

      for row in rows:
        if len(row) < 5:
          continue
        raw_id = row[0].strip()
        clean_id = raw_id.zfill(5) if raw_id.isdigit() else raw_id
        stn_name = row[1].strip()

        try:
          raw_val = float(row[4].strip())
          # 値が10倍されている場合の正規化（例: 285 -> 28.5）
          wbgt_val = raw_val / 10.0 if raw_val > 50 else raw_val
          wbgt_val = round(wbgt_val, 1)

          moe_by_id[clean_id] = wbgt_val
          if stn_name:
            moe_by_name[stn_name] = wbgt_val
        except ValueError:
          continue

      if moe_by_id:
        print(f"  -> 成功: 環境省から {len(moe_by_id)} 件の公式WBGTを取得しました。")
        moe_success = True
        break
    except Exception as e:
      print(f"  -> URL試行失敗 ({url}): {e}")

  if not moe_success:
    print(
        "  -> 警告: 環境省CSVの取得に失敗したため、気象庁アメダスの気温・湿度から計算補完を行います。"
    )

  # ---------------------------------------------------------
  # 2. 気象庁アメダス実測データの取得（404対策の遡り処理付き）
  # ---------------------------------------------------------
  print("[2/3] 気象庁アメダス実測データを取得中...")
  stn_table = {}
  amedas_data = {}
  latest_time_str = ""

  try:
    jma_headers = headers.copy()
    jma_headers["Referer"] = "https://www.jma.go.jp/"

    # 観測所リスト取得
    table_bytes = fetch_url(
        "https://www.jma.go.jp/bosai/amedas/const/amedastable.json", jma_headers
    )
    stn_table = json.loads(table_bytes.decode("utf-8"))

    # 最新時刻取得
    time_bytes = fetch_url(
        "https://www.jma.go.jp/bosai/amedas/data/latest_time.json", jma_headers
    )
    latest_time_str = json.loads(time_bytes.decode("utf-8"))

    digits = "".join([c for c in latest_time_str.split("+")[0] if c.isdigit()])
    dt = datetime.datetime.strptime(digits[:12], "%Y%m%d%H%M")

    # 気象庁のデータ反映ラグ（404）対策として最大40分前まで遡る
    for attempt in range(5):
      time_formatted = dt.strftime("%Y%m%d%H%M00")
      amedas_url = (
          f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"
      )
      try:
        amedas_bytes = fetch_url(amedas_url, jma_headers)
        amedas_data = json.loads(amedas_bytes.decode("utf-8"))
        latest_time_str = dt.strftime("%Y-%m-%dT%H:%M:00+09:00")
        print(f"  -> 成功: {dt.strftime('%H:%M')} のアメダス実測値を取得しました。")
        break
      except urllib.error.HTTPError as e:
        if e.code == 404:
          dt -= datetime.timedelta(minutes=10)
        else:
          raise e

    if not amedas_data:
      raise Exception(
          "気象庁サーバーから有効なアメダスデータが取得できませんでした。"
      )

  except Exception as e:
    print(f"【重大エラー】気象庁データの取得に失敗しました: {e}")
    sys.exit(1)

  # ---------------------------------------------------------
  # 3. データの結合と JSON 出力
  # ---------------------------------------------------------
  print("[3/3] データを結合して wbgt_data.json を生成中...")
  output_stations = {}

  for stn_id, st_info in stn_table.items():
    st_name = st_info.get("kjName", "")
    st_kana = st_info.get("knName", "")
    st_data = amedas_data.get(stn_id, {})

    temp = (
        st_data.get("temp", [None])[0]
        if isinstance(st_data.get("temp"), list)
        else None
    )
    humidity = (
        st_data.get("humidity", [None])[0]
        if isinstance(st_data.get("humidity"), list)
        else None
    )
    wind = (
        st_data.get("wind", [None])[0]
        if isinstance(st_data.get("wind"), list)
        else None
    )
    precip = (
        st_data.get("precipitation1h", [0])[0]
        if isinstance(st_data.get("precipitation1h"), list)
        else 0
    )

    clean_jma_id = stn_id.zfill(5) if stn_id.isdigit() else stn_id

    # 1. 環境省公式WBGT（ID一致） 2. 地点名一致 3. 気象庁データからの試算
    wbgt = moe_by_id.get(clean_jma_id)
    if wbgt is None and st_name in moe_by_name:
      wbgt = moe_by_name[st_name]
    if wbgt is None and temp is not None:
      hum_val = humidity if humidity is not None else 50
      wbgt = round(
          0.735 * temp + 0.0374 * hum_val + 0.00292 * temp * hum_val - 4.064, 1
      )

    if temp is not None:
      output_stations[stn_id] = {
          "name": st_name,
          "kana": st_kana,
          "temp": temp,
          "humidity": humidity,
          "wind": wind,
          "precip": precip if precip is not None else 0,
          "wbgt": wbgt,
      }

  if not output_stations:
    print("【重大エラー】有効な観測データが0件でした。")
    sys.exit(1)

  result = {"updated_at": latest_time_str, "stations": output_stations}

  with open("wbgt_data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

  print("==========================================")
  print(
      f" SUCCESS: {len(output_stations)}件のデータを wbgt_data.json"
      " に正常保存しました。"
  )
  print("==========================================")


if __name__ == "__main__":
  main()
