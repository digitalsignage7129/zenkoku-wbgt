#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
広島市安芸区(矢野町) 現場用 WBGT・気象情報 生成スクリプト
田原本町版/菊川市版と同じロジックで、定数のみ差し替えたもの。

【定数の根拠】
- 設置場所の座標(北緯34.31853, 東経132.54614)を国土地理院の逆ジオコーディングAPI
  (https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress?lat=..&lon=..)
  で照合した結果、muniCd=34107(広島市安芸区)・矢野町 と判定された。
  なお「安芸区」と「安芸郡」は名前が似ているが別の自治体で、
  安芸郡(府中町・海田町・熊野町・坂町など)の市区町村コードは34107ではなく
  30x台の別コードになるため混同しないよう注意(今回の座標は明確に安芸区側)。
- AMEDAS_CODE / MOE_POINT = "67437" (広島)
  環境省熱中症予防情報サイトの実URL
    https://www.wbgt.env.go.jp/sp/graph_ref_td.php?region=08&prefecture=67&point=67437
  のページタイトルが「環境省熱中症予防情報サイト 広島(広島)」であることを確認済み。
  安芸区(矢野町)からも至近距離にある広島市の公式観測点。
  JMA AMeDASの実況点としても有効であることを確認済み
  (気温24.6℃・湿度79%・風速2.1m/sなどの実データを取得できた)。
- REGION_CODE = "08" / PREF_CODE = "67" (広島県)
  上記の実URLで確認済み(region=08, prefecture=67)。
"""

import csv
import io
import json
import re
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone

# --- 広島市安芸区用設定 ---
AMEDAS_CODE = "67437"   # 広島 - JMA AMeDAS実況点
MOE_POINT = "67437"     # 同上 - 環境省WBGT観測地点
REGION_CODE = "08"      # 中国(環境省サイトの地域コード)
PREF_CODE = "67"        # 広島県
LOCATION_NAME = "広島県広島市安芸区"
OUTPUT_FILE = "akigun-wbgt.json"

JST = timezone(timedelta(hours=9))

UA_HEADER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# 検証をスキップするSSLコンテキスト(社内プロキシ等でのSSL検証エラー回避のため、
# 田原本町版・菊川市版と同じ設定を踏襲)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers=UA_HEADER)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as res:
        return res.read()


def get_amedas_weather():
    """
    JMA AMeDAS 10分値から気温・湿度・風速・簡易天気を取得する。
    直近10分値がまだ配信されていないことがあるため、10分刻みで最大60分前まで
    遡って最初に成功した時刻のデータを採用する。
    """
    now = datetime.now(JST)
    for back_min in range(10, 61, 10):
        t = now - timedelta(minutes=back_min)
        rounded_minute = (t.minute // 10) * 10
        t = t.replace(minute=rounded_minute, second=0, microsecond=0)
        time_str = t.strftime("%Y%m%d%H") + f"{t.minute:02d}00"
        url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_str}.json"
        try:
            raw = fetch_url(url)
            data = json.loads(raw)
            if AMEDAS_CODE not in data:
                continue
            point = data[AMEDAS_CODE]
            temp = point.get("temp", [None, None])[0]
            humidity = point.get("humidity", [None, None])[0]
            wind = point.get("wind", [None, None])[0]
            precip10m = point.get("precipitation10m", [0, None])[0] or 0
            sun10m = point.get("sun10m", [0, None])[0] or 0
            if precip10m is not None and precip10m >= 0.5:
                weather = "雨"
            elif sun10m is not None and sun10m >= 0.1:
                weather = "晴れ"
            else:
                weather = "くもり"
            return {
                "temperature": temp,
                "humidity": humidity,
                "wind_speed": wind,
                "weather": weather,
            }
        except Exception:
            continue
    return {"temperature": None, "humidity": None, "wind_speed": None, "weather": None}


def get_wbgt():
    """
    環境省WBGT実況値を取得する。
    第一手段: prev15d CSV(Shift-JIS)の最終行から数値を抽出。
    第二手段: グラフページ(HTML)を軽くスクレイピングして数値を抽出。
    """
    # 第一手段: CSV
    try:
        csv_url = f"https://www.wbgt.env.go.jp/prev15d/list/tbl/prev15d_{MOE_POINT}.csv"
        raw = fetch_url(csv_url)
        text = raw.decode("shift_jis", errors="ignore")
        reader = list(csv.reader(io.StringIO(text)))
        value = None
        for row in reversed(reader):
            for cell in reversed(row):
                cell = cell.strip()
                if re.match(r"^\d{2}\.\d", cell):
                    value = float(cell)
                    break
            if value is not None:
                break
        if value is not None:
            return value
    except Exception:
        pass

    # 第二手段: HTMLフォールバック
    try:
        html_url = (
            "https://www.wbgt.env.go.jp/sp/graph_ref_td.php"
            f"?region={REGION_CODE}&prefecture={PREF_CODE}&point={MOE_POINT}"
        )
        raw = fetch_url(html_url)
        text = raw.decode("utf-8", errors="ignore")
        matches = re.findall(r"\b([1-3][0-9]\.[0-9])\b", text)
        candidates = [float(m) for m in matches if 10.0 <= float(m) <= 40.0]
        if candidates:
            return candidates[-1]
    except Exception:
        pass

    return None


def wbgt_to_level(wbgt):
    if wbgt is None:
        return "--"
    if wbgt >= 31.0:
        return "危険"
    if wbgt >= 28.0:
        return "厳重警戒"
    if wbgt >= 25.0:
        return "警戒"
    if wbgt >= 21.0:
        return "留意"
    return "ほぼ安全"


def main():
    weather_data = get_amedas_weather()
    wbgt_value = get_wbgt()
    level = wbgt_to_level(wbgt_value)

    result = {
        "location": LOCATION_NAME,
        "wbgt": wbgt_value if wbgt_value is not None else "--.-",
        "level": level,
        "temperature": weather_data["temperature"] if weather_data["temperature"] is not None else "--.-",
        "humidity": weather_data["humidity"] if weather_data["humidity"] is not None else "--",
        "wind_speed": weather_data["wind_speed"] if weather_data["wind_speed"] is not None else "--.-",
        "weather": weather_data["weather"] or "不明",
        "updated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[{result['updated_at']}] {OUTPUT_FILE} を更新しました: {result}")


if __name__ == "__main__":
    main()
