from datetime import datetime
import io
import csv
import json
import requests

# ------------------------------------------------------------------
# 1. 地点マッピング定義 (環境省コード <-> 気象庁アメダスID & 地点名)
# ------------------------------------------------------------------
# 環境省の5桁コードと気象庁アメダスコードは基本的に共通ですが、
# 特殊な拠点や表記揺れに対応するためマッピングテーブルを保持します。
STATION_MAP = {
    "47412": {"jma_id": "47412", "name": "札幌", "pref": "北海道"},
    "47401": {"jma_id": "47401", "name": "稚内", "pref": "北海道"},
    "47575": {"jma_id": "47575", "name": "青森", "pref": "青森県"},
    "44132": {"jma_id": "44132", "name": "東京", "pref": "東京都"},
    "56227": {"jma_id": "56227", "name": "名古屋", "pref": "愛知県"},
    "62078": {"jma_id": "62078", "name": "大阪", "pref": "大阪府"},
    "82182": {"jma_id": "82182", "name": "福岡", "pref": "福岡県"},
    # 必要に応じて主要拠点・全拠点（約840地点）を追加可能
}


# ------------------------------------------------------------------
# 2. WBGTレベル（警戒度区分）判定ヘルパー
# ------------------------------------------------------------------
def get_wbgt_level(wbgt_value: float) -> str:
    """環境省基準に基づくWBGTレベル判定"""
    if wbgt_value < 21.0:
        return "ほぼ安全"
    elif wbgt_value < 25.0:
        return "留意"
    elif wbgt_value < 28.0:
        return "警戒"
    elif wbgt_value < 31.0:
        return "厳重警戒"
    else:
        return "危険"


# ------------------------------------------------------------------
# 3. 環境省 CSV パース処理
# ------------------------------------------------------------------
def fetch_and_parse_moe_csv() -> dict:
    """
    環境省 熱中症予防情報サイトから最新WBGT CSVをダウンロードしてパースする
    返り値: { "station_id": {"wbgt": float, "level": str, "updated_at": str} }
    """
    # 最新の実測値・推測値が配信されている公式CSV URL
    url = "https://www.wbgt.env.go.jp/est1570/d/wbgt_all_latest.csv"

    print("Fetching CSV from Ministry of the Environment (MoE)...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # 環境省のCSVは Shift-JIS または UTF-8（BOM付き）で配信されるためフォールバック処理
        try:
            content = response.content.decode("shift_jis")
        except UnicodeDecodeError:
            content = response.content.decode("utf-8-sig")

        parsed_wbgt = {}
        reader = csv.reader(io.StringIO(content))

        for row in reader:
            # 空行やヘッダー・コメント行のスキップ処理
            if not row or len(row) < 5 or row[0].startswith("#"):
                continue

            station_code = row[0].strip()
            date_str = row[1].strip()  # 例: "20260724"
            time_str = row[2].strip()  # 例: "16" または "1600"
            raw_val = row[3].strip()   # 例: "252" (25.2℃の意味) または "25.2"

            # 数値への変換 (10倍表記の整数形式と小数表記の両方に対応)
            try:
                wbgt_val = float(raw_val)
                if wbgt_val > 50:  # 10倍表示 (例: 252 -> 25.2)
                    wbgt_val = round(wbgt_val / 10.0, 1)
            except ValueError:
                continue

            # 日時のフォーマット整列 (YYYY-MM-DD HH:00)
            formatted_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str.zfill(2)[:2]}:00"

            parsed_wbgt[station_code] = {
                "wbgt": wbgt_val,
                "level": get_wbgt_level(wbgt_val),
                "updated_at": formatted_time
            }

        return parsed_wbgt

    except Exception as e:
        print(f"Error fetching/parsing MoE CSV: {e}")
        return {}


# ------------------------------------------------------------------
# 4. 気象庁 (JMA) アメダスデータ取得処理
# ------------------------------------------------------------------
def fetch_jma_amedas() -> dict:
    """気象庁公式アメダスJSON（最新値）を取得"""
    # 実際の実装では最新時刻（YYYYMMDDHH0000）を動的に計算してURLを生成します
    now_str = datetime.now().strftime("%Y%m%d%H0000")
    url = f"https://www.jma.go.jp/bosai/amedas/data/map/{now_str}.json"

    print("Fetching AMEDAS data from JMA...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching JMA data: {e}")
        return {}


# ------------------------------------------------------------------
# 5. データ統合・JSON出力処理
# ------------------------------------------------------------------
def build_hybrid_dataset():
    moe_wbgt_map = fetch_and_parse_moe_csv()
    jma_raw_data = fetch_jma_amedas()

    merged_stations = []

    # マッピングテーブルに登録された地点を順に処理
    for moe_id, meta in STATION_MAP.items():
        jma_id = meta["jma_id"]

        # 環境省データ（公式WBGT）
        wbgt_info = moe_wbgt_map.get(moe_id, {
            "wbgt": None,
            "level": "不明",
            "updated_at": None
        })

        # 気象庁アメダスデータ（気温・湿度・風速・雨量など）
        jma_info = jma_raw_data.get(jma_id, {})
        temp = jma_info.get("temp", [None])[0] if "temp" in jma_info else None
        humidity = jma_info.get("humidity", [None])[0] if "humidity" in jma_info else None
        wind = jma_info.get("wind", [None])[0] if "wind" in jma_info else None

        merged_stations.append({
            "station_id": moe_id,
            "jma_amedas_id": jma_id,
            "name": meta["name"],
            "prefecture": meta["pref"],
            # 環境省データ（一切計算せず公式値を採用）
            "moe_data": {
                "wbgt": wbgt_info["wbgt"],
                "level": wbgt_info["level"],
                "updated_at": wbgt_info["updated_at"]
            },
            # 気象庁アメダス実測データ
            "jma_data": {
                "temperature": temp,
                "humidity": humidity,
                "wind_speed": wind
            }
        })

    # 最終的なJSON出力
    output_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source_moe": "https://www.wbgt.env.go.jp/",
            "source_jma": "https://www.jma.go.jp/"
        },
        "stations": merged_stations
    }

    with open("wbgt_data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully merged {len(merged_stations)} stations into wbgt_data.json!")

if __name__ == "__main__":
    build_hybrid_dataset()
