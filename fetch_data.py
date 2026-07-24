import csv
import io
import json
import ssl
import sys
import urllib.request


def fetch_url(url, headers):
  """SSLチェックをスキップして安全にデータを入手する関数"""
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
    return res.read()


def main():
  print("GitHub Actions 上でデータ取得処理を開始します...")

  # 気象庁・環境省からアクセスを拒否されないためのヘッダー設定
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      ),
      "Accept": (
          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webkit,*/*;q=0.8"
      ),
      "Accept-Language": "ja-JP,ja;q=0.9",
      "Referer": "https://www.jma.go.jp/",
  }

  # ---------------------------------------------------------
  # 1. 環境省WBGTデータの取得
  # ---------------------------------------------------------
  moe_by_id = {}
  moe_by_name = {}
  moe_urls = [
      "https://www.wbgt.env.go.jp/est15d/dl/wbgt_all_latest.csv",
      "https://www.wbgt.env.go.jp/prev15d/dl/wbgt_all_latest.csv",
  ]

  for url in moe_urls:
    try:
      raw_bytes = fetch_url(url, headers)
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
          wbgt_val = raw_val / 10.0 if raw_val > 50 else raw_val
          moe_by_id[clean_id] = round(wbgt_val, 1)
          if stn_name:
            moe_by_name[stn_name] = round(wbgt_val, 1)
        except ValueError:
          continue

      if moe_by_id:
        print(f"環境省WBGTデータ取得成功: {len(moe_by_id)}件")
        break
    except Exception as e:
      print(f"環境省URL取得スキップ ({url}): {e}")

  # ---------------------------------------------------------
  # 2. 気象庁アメダスデータの取得
  # ---------------------------------------------------------
  try:
    # 観測所テーブル取得
    table_bytes = fetch_url(
        "https://www.jma.go.jp/bosai/amedas/const/amedastable.json", headers
    )
    stn_table = json.loads(table_bytes.decode("utf-8"))

    # 最新時刻取得
    time_bytes = fetch_url(
        "https://www.jma.go.jp/bosai/amedas/data/latest_time.json", headers
    )
    latest_time_str = json.loads(time_bytes.decode("utf-8"))

    # アメダス実測値取得
    time_formatted = (
        latest_time_str.replace("-", "")
        .replace(":", "")
        .replace("T", "")
        .split("+")[0]
    )
    amedas_url = (
        f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"
    )
    amedas_bytes = fetch_url(amedas_url, headers)
    amedas_data = json.loads(amedas_bytes.decode("utf-8"))

    print(
        f"気象庁データ取得成功 (観測所: {len(stn_table)}件, 時刻:"
        f" {latest_time_str})"
    )

  except Exception as e:
    print(f"【重大エラー】気象庁データの取得に失敗しました: {e}")
    sys.exit(1)

  # ---------------------------------------------------------
  # 3. データの結合処理
  # ---------------------------------------------------------
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

    # WBGT照合 (ID一致 -> 地点名一致 -> 推計)
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

  # 書き出し
  with open("wbgt_data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

  print(
      f"成功: {len(output_stations)}件のデータを wbgt_data.json に正常保存しました。"
  )


if __name__ == "__main__":
  main()
