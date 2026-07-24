import csv
import io
import json
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def main():
  url = "https://www.wbgt.env.go.jp/est1570/d/wbgt_all_latest.csv"
  print("Fetching MoE WBGT CSV...")

  res = requests.get(url, headers=HEADERS, timeout=10)
  res.raise_for_status()

  try:
    content = res.content.decode("shift_jis")
  except UnicodeDecodeError:
    content = res.content.decode("utf-8-sig")

  stations = []
  reader = csv.reader(io.StringIO(content))
  for row in reader:
    if not row or len(row) < 5 or row[0].startswith("#"):
      continue

    station_code = row[0].strip()
    # 環境省CSVは通常、地点名が後ろの列に含まれている、あるいはコードのみの場合は
    # あとで気象庁側と名前で突合するためコードとWBGTを保持します
    date_str = row[1].strip()
    time_str = row[2].strip()
    raw_val = row[3].strip()

    try:
      wbgt_val = float(raw_val)
      if wbgt_val > 50:
        wbgt_val = round(wbgt_val / 10.0, 1)
    except ValueError:
      continue

    if wbgt_val < 21.0:
      level = "ほぼ安全"
    elif wbgt_val < 25.0:
      level = "留意"
    elif wbgt_val < 28.0:
      level = "警戒"
    elif wbgt_val < 31.0:
      level = "厳重警戒"
    else:
      level = "危険"

    formatted_time = (
        f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        f" {time_str.zfill(2)[:2]}:00"
    )

    stations.append({
        "moe_code": station_code,
        "wbgt": wbgt_val,
        "level": level,
        "updated_at": formatted_time,
    })

  with open("moe_wbgt.json", "w", encoding="utf-8") as f:
    json.dump(stations, f, ensure_ascii=False, indent=2)

  print(f"✅ Saved {len(stations)} MoE records to moe_wbgt.json")


if __name__ == "__main__":
  main()
