import csv
import datetime
import io
import json
import ssl
import sys
import urllib.error
import urllib.request


def fetch_url(url, headers):
  """URLからデータを取得し、通信内容をログ出力する関数"""
  print(f"  [通信試行] {url}")
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
    return res.read()


def get_jma_data(headers):
  """気象庁アメダスデータを取得（反映ラグ対策で過去へ遡る）"""
  print("\n--- [1] 気象庁アメダスデータ取得 ---")

  # 1. 観測所テーブル取得
  table_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"
  try:
    table_bytes = fetch_url(table_url, headers)
    stn_table = json.loads(table_bytes.decode("utf-8"))
    print(f"  └ 観測所マスター取得成功 ({len(stn_table)} 地点)")
  except Exception as e:
    print(f"  ❌ 観測所マスター取得失敗: {e}")
    return None, None, None

  # 2. 最新観測時刻の取得
  time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.json"
  try:
    time_bytes = fetch_url(time_url, headers)
    latest_time_str = json.loads(time_bytes.decode("utf-8"))
    print(f"  └ 最新観測公称時刻: {latest_time_str}")
  except Exception as e:
    print(f"  ❌ 最新時刻取得失敗: {e}")
    return None, None, None

  # 時刻文字の解析
  digits = "".join([c for c in latest_time_str.split("+")[0] if c.isdigit()])
  dt = datetime.datetime.strptime(digits[:12], "%Y%m%d%H%M")

  # 3. アメダス実測値JSONの取得（404の場合は10分ずつ過去に遡る）
  amedas_data = None
  target_time_str = latest_time_str

  for i in range(6):  # 最大60分前までリトライ
    time_formatted = dt.strftime("%Y%m%d%H%M00")
    amedas_url = (
        f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"
    )
    try:
      data_bytes = fetch_url(amedas_url, headers)
      amedas_data = json.loads(data_bytes.decode("utf-8"))
      target_time_str = dt.strftime("%Y-%m-%dT%H:%M:00+09:00")
      print(f"  ✅ 取得成功: {dt.strftime('%H:%M')} のアメダス実測値を取得できました")
      break
    except urllib.error.HTTPError as e:
      if e.code == 404:
        print(f"  ⚠️ {dt.strftime('%H:%M')} のデータは未反映(404)。10分前を試します")
        dt -= datetime.timedelta(minutes=10)
      else:
        print(f"  ❌ HTTPエラー ({e.code}): {e}")
        break
    except Exception as e:
      print(f"  ❌ 通信エラー: {e}")
      break

  return stn_table, amedas_data, target_time_str


def get_moe_wbgt(headers):
  """環境省WBGTデータの取得"""
  print("\n--- [2] 環境省WBGTデータ取得 ---")
  moe_by_id = {}
  moe_by_name = {}

  candidate_urls = [
      "https://www.wbgt.env.go.jp/est15d/dl/wbgt_all_latest.csv",
      "https://www.wbgt.env.go.jp/prev15d/dl/wbgt_all_latest.csv",
  ]

  for url in candidate_urls:
    try:
      raw_bytes = fetch_url(url, headers)
      try:
        csv_text = raw_bytes.decode("cp932")
      except Exception:
        csv_text = raw_bytes.decode("utf-8", errors="ignore")

      f = io.StringIO(csv_text)
      reader = csv.reader(f)
      for row in reader:
        if len(row) < 5:
          continue
        raw_id = row[0].strip()
        clean_id = raw_id.zfill(5) if raw_id.isdigit() else raw_id
        stn_name = row[1].strip()
        try:
          raw_val = float(row[4].strip())
          val = round(raw_val / 10.0 if raw_val > 50 else raw_val, 1)
          moe_by_id[clean_id] = val
          if stn_name:
            moe_by_name[stn_name] = val
        except ValueError:
          continue

      if moe_by_id:
        print(f"  ✅ 成功: 環境省から {len(moe_by_id)} 件のWBGTを取得")
        return moe_by_id, moe_by_name
    except urllib.error.HTTPError as e:
      print(f"  ⚠️ CSV未開放・取得失敗 ({e.code})")
    except Exception as e:
      print(f"  ⚠️ エラー: {e}")

  return moe_by_id, moe_by_name


def main():
  print("==========================================")
  print(" データ取得処理を開始します ")
  print("==========================================")

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      ),
      "Accept": "*/*",
      "Accept-Language": "ja-JP,ja;q=0.9",
  }

  # 1. 気象庁アメダスデータ取得（必須）
  stn_table, amedas_data, updated_at = get_jma_data(headers)

  if not stn_table or not amedas_data:
    print(
        "\n【重大エラー】気象庁データの取得に失敗したため、処理を中断します。"
    )
    sys.exit(1)

  # 2. 環境省WBGT取得（取得できれば公式値を使用）
  moe_by_id, moe_by_name = get_moe_wbgt(headers)

  # 3. データ結合処理
  print("\n--- [3] データ結合および JSON 生成 ---")
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

    # WBGT値の判定（環境省データ ➔ なければ気温・湿度から近似計算）
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

  result = {"updated_at": updated_at, "stations": output_stations}

  with open("wbgt_data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

  print("==========================================")
  print(
      f" 🎉 成功: {len(output_stations)} 地点のデータを wbgt_data.json"
      " に保存しました！"
  )
  print("==========================================")


if __name__ == "__main__":
  main()
