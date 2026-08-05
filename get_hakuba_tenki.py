import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# tenki.jp 白馬村のURL候補（白馬村はエリア4820: 松本・大町地域）
CANDIDATE_URLS = [
    "https://tenki.jp/forecast/3/12/4820/20485/",
    "https://tenki.jp/forecast/3/12/4810/20485/",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def clean_num(text):
    """文字列から数値部分のみ抽出"""
    if not text:
        return "--"
    match = re.search(r"-?\d+", text)
    return match.group(0) if match else "--"


def clean_weather(text):
    """天気文字列の余分な改行・空白を除去"""
    if not text:
        return "--"
    return re.sub(r"\s+", "", text).strip()


def fetch_html():
    """URL候補からアクセス可能なページを取得"""
    for url in CANDIDATE_URLS:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            continue
    raise Exception("tenki.jp の白馬村ページを取得できませんでした。")


def get_tenki_data():
    html = fetch_html()
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "location": "長野県白馬村",
        "updated_at": "",
        "today": {"weather": "--", "temp_max": "--", "temp_min": "--", "pop": "--"},
        "tomorrow": {
            "weather": "--",
            "temp_max": "--",
            "temp_min": "--",
            "pop": "--",
        },
        "day_after": {
            "weather": "--",
            "temp_max": "--",
            "temp_min": "--",
            "pop": "--",
        },
    }

    # --- 1. 今日・明日のデータ取得 ---
    sections = [
        ("today", soup.find("section", class_="today-weather")),
        ("tomorrow", soup.find("section", class_="tomorrow-weather")),
    ]

    for key, sec in sections:
        if not sec:
            continue

        # 天気
        weather_el = sec.find("p", class_="weather-telop")
        if weather_el:
            result[key]["weather"] = clean_weather(weather_el.text)

        # 最高気温
        high_el = sec.find("dd", class_="high-temp")
        if high_el:
            val = high_el.find("span", class_="value")
            if val:
                result[key]["temp_max"] = clean_num(val.text)

        # 最低気温
        low_el = sec.find("dd", class_="low-temp")
        if low_el:
            val = low_el.find("span", class_="value")
            if val:
                result[key]["temp_min"] = clean_num(val.text)

        # 降水確率（時間帯ごとの最大値を取る）
        precip_table = sec.find("table", class_="precip-table")
        if precip_table:
            pops = []
            for td in precip_table.find_all("td"):
                txt = clean_num(td.text)
                if txt.isdigit():
                    pops.append(int(txt))
            if pops:
                result[key]["pop"] = str(max(pops))

    # --- 2. 明後日のデータ取得 (週間予報エリアから抽出) ---
    week_table = soup.find("table", class_="forecast-point-week-table")
    if week_table:
        rows = week_table.find_all("tr")

        for row in rows:
            # 天気
            if "weather" in row.get("class", []):
                tds = row.find_all("td")
                if len(tds) > 2:
                    img = tds[2].find("img")
                    txt = img.get("alt") if img else tds[2].text
                    result["day_after"]["weather"] = clean_weather(txt)

            # 最高気温
            elif "high-temp" in row.get("class", []):
                tds = row.find_all("td")
                if len(tds) > 2:
                    result["day_after"]["temp_max"] = clean_num(tds[2].text)

            # 最低気温
            elif "low-temp" in row.get("class", []):
                tds = row.find_all("td")
                if len(tds) > 2:
                    result["day_after"]["temp_min"] = clean_num(tds[2].text)

            # 降水確率
            elif "precip" in row.get("class", []):
                tds = row.find_all("td")
                if len(tds) > 2:
                    result["day_after"]["pop"] = clean_num(tds[2].text)

    # 更新時刻
    jst = timezone(timedelta(hours=9))
    result["updated_at"] = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    # JSONへ書き出し
    with open("hakuba_tenki.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("hakuba_tenki.json を正常に更新しました:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    get_tenki_data()
