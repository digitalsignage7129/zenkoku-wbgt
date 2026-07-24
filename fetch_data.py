import csv
import datetime
import io
import json
import ssl
import sys
import urllib.error
import urllib.request


def fetch_url(url, headers):
  """指定URLからバイナリデータを取得する関数"""
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
    return res.read()


def get_jma_data(headers):
  """気象庁アメダスデータを取得（現在時刻から10分刻みで過去へ自動探索）"""
  print("\n--- [1] 気象庁アメダスデータ取得 ---")

  # 1. 観測所マスター取得
  table_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"
  try:
    print(f"  [通信試行] {table_url}")
    table_bytes = fetch_url(table_url, headers)
    stn_table = json.loads(table_bytes.decode("utf-8"))
    print(f"  └ 観測所マスター取得成功 ({len(stn_table)} 地点)")
  except Exception as e:
    print(f"  ❌ 観測所マスター取得失敗: {e}")
    return None, None, None

  # 2. 日本時間(JST)の現在時刻から、直近の10分刻みの時刻を計算
  jst = datetime.timezone(datetime.timedelta(hours=9))
  now_jst = datetime.datetime.now(jst)

  # 10分単位に切り下げ (例: 16:14 -> 16:10)
  minute = (now_jst.minute // 10) * 10
  target_dt = now_jst.replace(minute=minute, second=0, microsecond=0)

  amedas_data = None
  latest_time_str = ""

  print(
      f"  [探索開始] 現在時刻 JST"
      f" {now_jst.strftime('%Y-%m-%d %H:%M:%S')} から最新データを探索します..."
  )

  # サーバー上の反映待ち(404)に備えて最大12回(2時間分)過去へ遡る
  for attempt in range(12):
    time_formatted = target_dt.strftime("%Y%m%d%H%M00")
    amedas_url = (
        f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"
    )
    print(f"  [通信試行] {amedas_url}")
    try:
      data_bytes = fetch_url(amedas_url, headers)
      amedas_data = json.loads(data_bytes.decode("utf-8"))
      latest_time_str = target_dt.strftime("%Y-%m-%dT%H:%M:00+09:00")
      print(
          f"  ✅ 取得成功: {target_dt.strftime('%H:%M')}"
          " のアメダス実測値データの取得に成功しました！"
      )
      break
    except urllib.error.HTTPError as e:
      if e.code == 404:
        prev_dt = target_dt - datetime.timedelta(minutes=10)
        print(
            f"  ⚠️ {target_dt.strftime('%H:%M')} は未配信(404)。10分前"
            f" ({prev_dt.strftime('%H:%M')}) を試します"
        )
        target_dt = prev_dt
      else:
        print(f"  ❌ HTTPエラー ({e.code}): {e}")
        break
    except Exception as e:
      print(f"  ❌ 通信エラー: {e}")
      break

  return stn_table, amedas_data, latest_time_str


def get_moe_wbgt(headers):
  """環境省WBGTデータの取得"""
  print("\n--- [2] 環境省WBGTデータ取得 ---")
  moe_by_id = {}
  moe_by_name = {}

  candidate_urls = [
      "https://www.wbgt.env.go.jp/prev15d/dl/wbgt_all_latest.csv",
      "https://www.wbgt.env.go.jp/est15d/dl/wbgt_all_latest.csv",
      "https://www.wbgt.env.go.jp/day/dl/wbgt_all_latest.csv",
  ]

  for url in candidate_urls:
    print(f"  [通信試行] {url}")
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
        print(
            f"  ✅ 成功: 環境省公式CSVから {len(moe_by_id)} 件のWBGTを取得しました"
        )
        return moe_by_id, moe_by_name
    except urllib.error.HTTPError as e:
      print(f"  ⚠️ CSV未開放・取得不可 ({e.code})")
    except Exception as e:
      print(f"  ⚠️ エラー: {e}")

  print(
      "  ℹ️"
      " 環境省の全体CSVがダウンロードできないため、気象庁アメダス実測値（気温・湿度）からWBGT（日本生気象学会算出式）を計算します"
  )
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
        "\n【重大エラー】気象庁アメダスデータの取得に失敗したため、処理を中断します。"
    )
    sys.exit(1)

  # 2. 環境省WBGT取得
  moe_by_id, moe_by_name = get_moe_wbgt(headers)

  # 3. データ結合処理
  print("\n--- [3] データ結合および JSON 生成 ---")
  output_stations = {}
  moe_count = 0
  calc_count = 0

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

    # WBGT判定（1. 環境省ID 2. 地点名 3. 日本生気象学会式での算出）
    wbgt = moe_by_id.get(clean_jma_id)
    if wbgt is None and st_name in moe_by_name:
      wbgt = moe_by_name[st_name]

    if wbgt is not None:
      moe_count += 1
    elif temp is not None:
      hum_val = humidity if humidity is not None else 50
      # 小野・小野寺等の推定式 (WBGT = 0.735*T + 0.0374*RH + 0.00292*T*RH - 4.064)
      wbgt = round(
          0.735 * temp + 0.0374 * hum_val + 0.00292 * temp * hum_val - 4.064, 1
      )
      calc_count += 1

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
  print(" 🎉 SUCCESS: wbgt_data.json の生成に成功しました！")
  print(f" ├ 総観測地点数: {len(output_stations)} 地点")
  print(f" ├ 環境省公式WBGT適用: {moe_count} 地点")
  print(f" └ 気温・湿度からのWBGT算出: {calc_count} 地点")
  print("==========================================")


if __name__ == "__main__":
  main()
