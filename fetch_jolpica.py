import requests
import os
import time
from statistics import median

BASE = "https://api.jolpi.ca/ergast/f1"

DRIVER_IDS = {
    "Ayrton Senna":        "senna",
    "Alain Prost":         "prost",
    "Lewis Hamilton":      "hamilton",
    "Michael Schumacher":  "michael_schumacher",
    "Max Verstappen":      "max_verstappen",
    "Sebastian Vettel":    "vettel",
    "Fernando Alonso":     "alonso",
    "Niki Lauda":          "lauda",
    "Jenson Button":       "button",
    "Kimi Räikkönen":      "raikkonen",
    "Damon Hill":          "hill",
    "Mika Häkkinen":       "hakkinen",
    "Nigel Mansell":       "mansell",
}

SEASONS = list(range(2018, 2025))

NOTABLE_RACES = [
    (2021, 22),   # Abu Dhabi 2021
    (2020, 15),   # Bahrain 2020
]

os.makedirs("data", exist_ok=True)


def fetch_json(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=20,
                         headers={"User-Agent": "f1-rag-project/1.0"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  request error: {e}")
        return None


def fetch_all_pages(url):
    """Jolpica defaults to 30 results per page so we need to paginate"""
    all_races = []
    offset = 0
    limit = 100
    while True:
        data = fetch_json(url, params={"limit": limit, "offset": offset})
        if not data:
            break
        mr = data["MRData"]
        races = mr.get("RaceTable", {}).get("Races", [])
        all_races.extend(races)
        total = int(mr.get("total", 0))
        offset += limit
        if offset >= total:
            break
        time.sleep(0.3)
    return all_races


def lap_to_seconds(t):
    try:
        if ":" in t:
            mins, rest = t.split(":")
            return int(mins) * 60 + float(rest)
        return float(t)
    except Exception:
        return None


# ── Driver career stats ───
print("=== Fetching driver career stats ===")

career_stats = {}

for name, driver_id in DRIVER_IDS.items():
    print(f"  {name}...")
    races = fetch_all_pages(f"{BASE}/drivers/{driver_id}/results/")

    wins = podiums = poles = race_count = 0
    for race in races:
        for res in race.get("Results", []):
            pos  = res.get("position", "")
            grid = res.get("grid", "")
            race_count += 1
            if pos == "1":
                wins += 1
            if pos in ("1", "2", "3"):
                podiums += 1
            if grid == "1":
                poles += 1

    career_stats[name] = {"wins": wins, "podiums": podiums, "poles": poles, "races": race_count}

    text = "\n".join([
        f"{name} — Career Statistics\n",
        f"Total race starts: {race_count}",
        f"Race wins: {wins}",
        f"Podium finishes (top 3): {podiums}",
        f"Pole positions (started from grid 1): {poles}",
    ]) + "\n"

    fname = f"data/jolpica_{driver_id}_career.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"    {fname}  ({race_count} races, {wins} wins, {podiums} podiums)")
    time.sleep(0.5)

# extra comparison passage — directly fixes the "who had more podiums" failure case
if "Ayrton Senna" in career_stats and "Alain Prost" in career_stats:
    s = career_stats["Ayrton Senna"]
    p = career_stats["Alain Prost"]
    more_podiums = "Senna" if s["podiums"] > p["podiums"] else "Prost"

    text = (
        "Senna vs Prost — Head to Head Career Comparison\n\n"
        f"Ayrton Senna: {s['races']} starts, {s['wins']} wins, "
        f"{s['podiums']} podiums, {s['poles']} pole positions\n"
        f"Alain Prost: {p['races']} starts, {p['wins']} wins, "
        f"{p['podiums']} podiums, {p['poles']} pole positions\n\n"
        f"Prost had more career race wins ({p['wins']}) compared to Senna ({s['wins']}).\n"
        f"{more_podiums} had more career podium finishes "
        f"({max(s['podiums'], p['podiums'])} vs {min(s['podiums'], p['podiums'])}).\n"
        f"Senna had significantly more pole positions ({s['poles']}) than Prost ({p['poles']}).\n"
    )
    with open("data/jolpica_senna_prost_comparison.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("  wrote jolpica_senna_prost_comparison.txt")


# ── Season race results ────
print("\n=== Fetching season race results ===")

for year in SEASONS:
    print(f"  {year}...")
    races = fetch_all_pages(f"{BASE}/{year}/results/")

    if not races:
        print(f"    no data for {year}, skipping")
        continue

    lines = [f"{year} Formula One Season — Race Results\n"]
    for race in races:
        lines.append(f"\nRound {race.get('round','?')}: {race.get('raceName','?')} ({race.get('date','?')})")
        for res in race.get("Results", [])[:5]:
            pos   = res.get("position", "?")
            drv   = res.get("Driver", {})
            ctor  = res.get("Constructor", {}).get("name", "?")
            dname = f"{drv.get('givenName','')} {drv.get('familyName','')}".strip()
            t     = res.get("Time", {}).get("time", res.get("status", ""))
            lines.append(f"  P{pos}: {dname} ({ctor})  {t}")

    fname = f"data/jolpica_season_{year}_results.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    saved {fname}  ({len(races)} races)")
    time.sleep(0.6)


# ── Notable race lap analysis ───
print("\n=== Fetching lap data for notable races ===")

for year, rnd in NOTABLE_RACES:
    print(f"  {year} round {rnd}...")

    all_laps = []
    offset = 0
    limit  = 200
    url    = f"{BASE}/{year}/{rnd}/laps/"
    while True:
        data = fetch_json(url, params={"limit": limit, "offset": offset})
        if not data:
            break
        races = data["MRData"].get("RaceTable", {}).get("Races", [])
        if not races:
            break
        all_laps.extend(races[0].get("Laps", []))
        total = int(data["MRData"].get("total", 0))
        offset += limit
        if offset >= total:
            break
        time.sleep(0.3)

    if not all_laps:
        print("    no lap data found")
        continue

    rdata      = fetch_json(f"{BASE}/{year}/{rnd}/results/")
    race_name  = "Unknown"
    if rdata:
        rl = rdata["MRData"].get("RaceTable", {}).get("Races", [])
        if rl:
            race_name = rl[0].get("raceName", race_name)
    time.sleep(0.4)

    lap_avgs = {}
    for lap in all_laps:
        lap_num = int(lap.get("number", 0))
        times_s = [v for v in (lap_to_seconds(t["time"]) for t in lap.get("Timings", [])) if v is not None]
        if times_s:
            lap_avgs[lap_num] = sum(times_s) / len(times_s)

    if not lap_avgs:
        print("    couldn't parse lap times")
        continue

    normal_laps = [float(t) for t in lap_avgs.values() if t < 200]  # <200s filters formation/outlap spikes
    if not normal_laps:
        continue
    median_time = median(normal_laps)
    # laps >1.6x the median are almost certainly under safety car or red flag
    slow_laps   = sorted([n for n, t in lap_avgs.items() if t > median_time * 1.6])
    total_laps  = max(lap_avgs.keys())

    lines = [
        f"{year} {race_name} — Lap Time Analysis\n",
        f"Total laps: {total_laps}",
        f"Median lap time (normal racing): {median_time:.3f}s ({median_time/60:.0f}m{median_time%60:.1f}s)",
    ]

    if slow_laps:
        lines.append(f"Laps with significantly reduced pace (safety car / red flag period): {', '.join(str(n) for n in slow_laps)}")
        if len(slow_laps) > 1:
            lines.append(
                f"The pace reduction started on lap {slow_laps[0]} and lasted until "
                f"approximately lap {slow_laps[-1]}, suggesting a safety car or VSC "
                f"was deployed from lap {slow_laps[0]}."
            )
    else:
        lines.append("No significant slow lap periods detected — likely a clean race.")

    lines.append("\nRace winner and top 3:")
    if rdata:
        rl = rdata["MRData"].get("RaceTable", {}).get("Races", [])
        if rl:
            for res in rl[0].get("Results", [])[:3]:
                drv   = res.get("Driver", {})
                dname = f"{drv.get('givenName','')} {drv.get('familyName','')}".strip()
                lines.append(f"  P{res.get('position','?')}: {dname} ({res.get('Constructor',{}).get('name','?')})")

    fname = f"data/jolpica_{year}_r{rnd}_lap_analysis.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    saved {fname}")
    time.sleep(0.5)

print("\ndone — jolpica data saved to data/jolpica_*.txt")
print("run ingest.py again to re-build the index with the new data")
