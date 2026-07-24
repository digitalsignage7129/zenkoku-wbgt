import json
import urllib.request
import csv
import io
import ssl

def main():
    print("==========================================")
    print(" WBGT & アメダスデータ取得処理を開始します ")
    print("==========================================")

    # SSL証明書エラー（ブロック）を回避
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # ---------------------------------------------------------
    # 1. 環境省から公式WBGTを取得
    # ---------------------------------------------------------
    moe_by_id = {}
    moe_by_name = {}

    moe_urls = [
        "https://www.wbgt.env.go.jp/est15d/dl/wbgt_all_latest.csv",
        "https://www.wbgt.env.go.jp/prev15d/dl/wbgt_all_latest.csv"
    ]

    print("[1/3] 環境省の公式WBGTデータをダウンロード中...")
    for url in moe_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as res:
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
                    raw_id = row[0].strip()
                    clean_id = raw_id.zfill(5) if raw_id.isdigit() else raw_id
                    stn_name = row[1].strip()

                    try:
                        raw_val = float(row[4].strip())
                        wbgt_val = raw_val / 10.0 if raw_val > 50 else raw_val
                        wbgt_val = round(wbgt_val, 1)

                        moe_by_id[clean_id] = wbgt_val
                        if stn_name:
                            moe_by_name[stn_name] = wbgt_val
                    except ValueError:
                        continue

            if moe_by_id:
                print(f"  -> 成功: 環境省から {len(moe_by_id)} 件のWBGTを取得しました。")
                break
        except Exception as e:
            print(f"  -> 警告: 環境省URLからの取得スキップ ({e})")

    # ---------------------------------------------------------
    # 2. 気象庁からアメダス実測値（気温・湿度・風速・雨量）を取得
    # ---------------------------------------------------------
    stn_table = {}
    latest_time_str = ""
    amedas_data = {}

    print("[2/3] 気象庁アメダス実測データをダウンロード中...")
    try:
        # 観測所テーブル取得
        req_table = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/const/amedastable.json", headers=headers)
        with urllib.request.urlopen(req_table, context=ctx, timeout=10) as res:
            stn_table = json.loads(res.read().decode())
        print(f"  -> 観測所リスト取得成功 ({len(stn_table)} 地点)")

        # 最新時刻取得
        req_time = urllib.request.Request("https://www.jma.go.jp/bosai/amedas/data/latest_time.json", headers=headers)
        with urllib.request.urlopen(req_time, context=ctx, timeout=10) as res:
            latest_time_str = json.loads(res.read().decode())
        print(f"  -> 最新観測時刻: {latest_time_str}")

        # 実測値取得
        time_formatted = latest_time_str.replace("-", "").replace(":", "").replace("T", "").split("+")[0]
        amedas_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_formatted}.json"

        req_amedas = urllib.request.Request(amedas_url, headers=headers)
        with urllib.request.urlopen(req_amedas, context=ctx, timeout=10) as res:
            amedas_data = json.loads(res.read().decode())
        print("  -> アメダス実測値の取得成功")

    except Exception as e:
        print(f"  -> エラー: 気象庁データの取得中に問題が発生しました: {e}")

    # ---------------------------------------------------------
    # 3. データの結合と JSON 出力（必ずファイルを出力する）
    # ---------------------------------------------------------
    print("[3/3] データを結合して wbgt_data.json を生成中...")
    output_stations = {}

    for stn_id, st_info in stn_table.items():
        st_name = st_info.get("kjName", "")
        st_kana = st_info.get("knName", "")
        st_data = amedas_data.get(stn_id, {})

        temp = st_data.get("temp", [None])[0] if isinstance(st_data.get("temp"), list) else None
        humidity = st_data.get("humidity", [None])[0] if isinstance(st_data.get("humidity"), list) else None
        wind = st_data.get("wind", [None])[0] if isinstance(st_data.get("wind"), list) else None
        precip = st_data.get("precipitation1h", [0])[0] if isinstance(st_data.get("precipitation1h"), list) else 0

        clean_jma_id = stn_id.zfill(5) if stn_id.isdigit() else stn_id

        # WBGT取得（ID一致 -> 地点名一致 -> 推計フォールバック）
        wbgt = moe_by_id.get(clean_jma_id)
        if wbgt is None and st_name in moe_by_name:
            wbgt = moe_by_name[st_name]
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
        "updated_at": latest_time_str if latest_time_str else "データ取得日時不明",
        "stations": output_stations
    }

    try:
        with open("wbgt_data.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("==========================================")
        print(" SUCCESS: wbgt_data.json の生成に成功しました！")
        print(f" (保存件数: {len(output_stations)} 地点)")
        print("==========================================")
    except Exception as e:
        print(f" FATAL ERROR: ファイルの保存に失敗しました: {e}")

if __name__ == "__main__":
    main()
