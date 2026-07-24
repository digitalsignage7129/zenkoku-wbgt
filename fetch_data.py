import json
import urllib.request
import csv
import io

def main():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # ---------------------------------------------------------
    # 1. 環境省から公式WBGTを取得（ID用と地点名用の2つの辞書を作成）
    # ---------------------------------------------------------
    moe_by_id = {}    # ID(5桁ゼロ埋め) -> WBGT
    moe_by_name = {}  # 地点名(漢字) -> WBGT

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
                    
                    # 1. IDを5桁のゼロ埋め文字列に正規化 (例: "4101" -> "04101")
                    raw_id = row[0].strip()
                    clean_id = raw_id.zfill(5) if raw_id.isdigit() else raw_id
                    
                    # 2. 地点名取得
                    stn_name = row[1].strip()

                    try:
                        raw_val = float(row[4].strip())
                        wbgt_val = raw_val / 10.0 if raw_val > 50 else raw_val
                        wbgt_val = round(wbgt_val, 1)

                        # 二重マッピング登録
                        moe_by_id[clean_id] = wbgt_val
                        if stn_name:
                            moe_by_name[stn_name] = wbgt_val

                    except ValueError:
                        continue

            if moe_by_id:
                print(f"環境省から {len(moe_by_id)} 件の公式WBGTデータをロードしました。")
                break
        except Exception as e:
            print(f"環境省URL取得スキップ ({url}): {e}")

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
    # 3. 二重照合（ID正規化一致 ➔ 地点名一致）で結合
    # ---------------------------------------------------------
    output_stations = {}

    for stn_id, st_info in stn_table.items():
        st_name = st_info.get("kjName", "")
        st_kana = st_info.get("knName", "")
        st_data = amedas_data.get(stn_id, {})

        # アメダス実測値の抽出
        temp = st_data.get("temp", [None])[0] if isinstance(st_data.get("temp"), list) else None
        humidity = st_data.get("humidity", [None])[0] if isinstance(st_data.get("humidity"), list) else None
        wind = st_data.get("wind", [None])[0] if isinstance(st_data.get("wind"), list) else None
        precip = st_data.get("precipitation1h", [0])[0] if isinstance(st_data.get("precipitation1h"), list) else 0

        # 気象庁IDの正規化 (5桁ゼロ埋め)
        clean_jma_id = stn_id.zfill(5) if stn_id.isdigit() else stn_id

        # 照合1: ID正規化マッチ
        wbgt = moe_by_id.get(clean_jma_id)

        # 照合2: 地点名(漢字)フォールバックマッチ
        if wbgt is None and st_name in moe_by_name:
            wbgt = moe_by_name[st_name]

        # 照合3: それでも取れない極小観測所の場合の安全策推計
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

    print("データ結合・JSON生成に成功しました。")

if __name__ == "__main__":
    main()
