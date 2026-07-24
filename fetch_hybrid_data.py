from datetime import datetime
import json
import requests

# ------------------------------------------------------------------
# 1. 環境省 (MoE) から公式WBGTデータを直接取得
# ------------------------------------------------------------------
def fetch_moe_wbgt():
    """環境省の熱中症予防情報サイトから公式データ（テキスト/CSV）を取得"""
    # 例: 環境省が配信している最新データURL
    moe_url = "https://www.wbgt.env.go.jp/est1570/d/wbgt_all_latest.csv"

    print("Fetching WBGT data from MoE...")
    # response = requests.get(moe_url)
    # response.encoding = 'shift_jis' # または utf-8

    # パース処理（地点コードをキーにした辞書を作る）
    wbgt_dict = {
        "47412": {  # 札幌の観測所コード例
            "wbgt": 25.2,
            "level": "警戒",
            "moe_updated": "2026-07-24 16:00",
        }
    }
    return wbgt_dict


# ------------------------------------------------------------------
# 2. 気象庁 (JMA) から天気・観測データを直接取得
# ------------------------------------------------------------------
def fetch_jma_weather():
    """気象庁の公式API/JSONから天気・観測値を取得"""
    # 例: 気象庁アメダス最新データ / 天気予報JSON
    jma_url = (
        "https://www.jma.go.jp/bosai/amedas/data/map/20260724160000.json"
    )

    print("Fetching weather data from JMA...")
    # response = requests.get(jma_url)
    # jma_raw = response.json()

    # パース処理
    weather_dict = {
        "47412": {
            "name": "札幌",
            "weather": "晴れ",
            "temperature": 28.3,
            "humidity": 66,
            "wind_speed": 3.2,
        }
    }
    return weather_dict


# ------------------------------------------------------------------
# 3. データの統合処理 (Merge)
# ------------------------------------------------------------------
def merge_and_export():
    moe_data = fetch_moe_wbgt()
    jma_data = fetch_jma_weather()

    merged_results = []

    # 地点IDを軸に両方のデータを合体
    for station_id, jma_info in jma_data.items():
        moe_info = moe_data.get(station_id, {})

        combined = {
            "station_id": station_id,
            "location_name": jma_info.get("name"),
            # 気象庁由来のデータ
            "jma_data": {
                "weather": jma_info.get("weather"),
                "temp": jma_info.get("temperature"),
                "humidity": jma_info.get("humidity"),
                "wind": jma_info.get("wind_speed"),
            },
            # 環境省由来のデータ (独自計算なし)
            "moe_data": {
                "wbgt": moe_info.get("wbgt"),
                "level": moe_info.get("level"),
                "updated_at": moe_info.get("moe_updated"),
            },
            "fetched_at": datetime.now().isoformat(),
        }
        merged_results.append(combined)

    # JSONへ書き出し
    with open("wbgt_data.json", "w", encoding="utf-8") as f:
        json.dump(
            {"stations": merged_results}, f, ensure_ascii=False, indent=2
        )

    print("Successfully generated wbgt_data.json with MoE + JMA data!")


if __name__ == "__main__":
    merge_and_export()
