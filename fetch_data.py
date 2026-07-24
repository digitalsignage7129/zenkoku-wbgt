import json
import urllib.request
import csv
import io

def main():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # ---------------------------------------------------------
    # 1. 環境省から公式WBGT実測・推定値CSVを取得
    # ---------------------------------------------------------
    moe_wbgt_map = {}
    moe_urls = [
        "https://www.wbgt.env.go.jp/est15d/dl/wbgt_all_latest.csv",
        "https://www.wbgt.env.go.jp/prev15d/dl/wbgt_all_latest.csv"
    ]

    for url in moe_urls:
        try:
            req_moe = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req_moe, timeout=10) as res:
                raw_bytes = res.read()
                try:
                    csv_text = raw_bytes.decode('cp932')
                except Exception:
                    csv_text = raw_bytes.decode('utf-8', errors='ignore')

                f = io.StringIO(csv_text)
                reader = csv.reader(f)
                rows = list(reader)

                for row in rows:
                    if len(row) < 5:
                        continue
                    stn_id = row[0].strip()
                    try:
                        raw_val = float(row[4].strip())
                        wbgt_val = raw_val / 10.0 if raw_val > 50 else raw_val
                        moe_wbgt_map[stn_id] = round(wbgt_val, 1)
                    except ValueError:
                        continue

            if moe_wbgt_map:
                print(f"環境省から {len(moe_wbgt_map)} 件の公式WBGTを取得完了")
                break
        except Exception as e:
            print(f"環境省URL ({url}) 取得失敗: {e}")

    # ---------------------------------------------------------
    # 2. 気象庁からアメダス実測値（気温・湿度・風速・雨量）を取得
    # ---------------------------------------------------------
    try:
        req_table = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/const/amedastable.json", headers=headers)
        with urllib.request.urlopen(req_table, timeout=10) as res:
            stn_table = json.loads(res.read().decode())

        req_time = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/data/latest_time.json", headers=headers)
        with urllib.request.urlopen(req_time, timeout=10) as res:
            latest_time_str = json.loads(res.read().decode())

        time_formatted = latest_time_str.replace("-", "").replace(":", "").replace("T", "").split("+")[0]
        amedas_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"

        req_amedas = urllib.request.Request(amedas_url, headers=headers)
        with urllib.request.urlopen(req_amedas, timeout=10) as res:
            amedas_data = json.loads(res.read().decode())
    except Exception as e:
        print(f"気象庁データ取得エラー: {e}")
        return

    # ---------------------------------------------------------
    # 3. 2つのデータを統合して JSON を生成
    # ---------------------------------------------------------
    output_stations = {}

    for stn_id, st_info in stn_table.items():
        st_name = st_info.get("kjName", "")
        st_kana = st_info.get("knName", "")
        st_data = amedas_data.get(stn_id, {})

        # 気象庁アメダスの実測値
        temp = st_data.get("temp", [None])[0] if isinstance(st_data.get("temp"), list) else None
        humidity = st_data.get("humidity", [None])[0] if isinstance(st_data.get("humidity"), list) else None
        wind = st_data.get("wind", [None])[0] if isinstance(st_data.get("wind"), list) else None
        precip = st_data.get("precipitation1h", [0])[0] if isinstance(st_data.get("precipitation1h"), list) else 0

        # 環境省の公式WBGT（存在しない小さな観測所の場合はアメダス実測から補正）
        wbgt = moe_wbgt_map.get(stn_id)
        if wbgt is None and temp is not None:
            hum_val = humidity if humidity is not None else 50
            wbgt = round(0.735 * temp + 0.0374 * hum_val + 0.00292 * temp * hum_val - 4.064, 1)

        if temp is not None:
            output_stations[stn_id] = {
                "name": st_name,
                "kana": st_kana,
                "temp": temp,
                "humidity": humidity,
                "wind": wind,
                "precip": precip if precip is not None else 0,
                "wbgt": wbgt
            }

    result = {
        "updated_at": latest_time_str,
        "stations": output_stations
    }

    with open("wbgt_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("wbgt_data.json の生成に成功しました。")

if __name__ == "__main__":
    main()
