import wikipediaapi
import requests
import os
import time
import json

# ── Wikipedia ──────────────────────────────────────────────────────────────
wiki = wikipediaapi.Wikipedia(
    user_agent="f1-rag-project/1.0",
    language="en"
)

WIKI_ARTICLES = [
    # drivers
    "Max Verstappen", "Lewis Hamilton", "Ayrton Senna",
    "Michael Schumacher", "Fernando Alonso", "Sebastian Vettel",
    "Niki Lauda", "Alain Prost", "Charles Leclerc",
    "Lando Norris", "Romain Grosjean",
    "Jenson Button", "Kimi Räikkönen", "Damon Hill",
    "Mika Häkkinen", "Nigel Mansell", "Rubens Barrichello",
    "George Russell (racing driver)", "Carlos Sainz Jr.",
    "Oscar Piastri", "Valtteri Bottas",
    # teams
    "Red Bull Racing", "Scuderia Ferrari", "McLaren",
    "Mercedes AMG Petronas Formula One Team", "Williams Racing",
    "Aston Martin F1 Team", "Alpine F1 Team", "Haas F1 Team",
    "Renault in Formula One", "Lotus Cars",
    # seasons
    "2021 Formula One World Championship",
    "2023 Formula One World Championship",
    "1994 Formula One World Championship",
    "2016 Formula One World Championship",
    "2020 Formula One World Championship",
    "2022 Formula One World Championship",
    "2008 Formula One World Championship",
    "2003 Formula One World Championship",
    "2012 Formula One World Championship",
    # circuits
    "Circuit de Monaco", "Silverstone Circuit",
    "Autodromo Nazionale Monza", "Circuit de Spa-Francorchamps",
    "Suzuka Circuit", "Bahrain International Circuit",
    "Circuit of the Americas", "Autódromo José Carlos Pace",
    "Hungaroring", "Circuit Gilles Villeneuve",
    # topics
    "Formula One regulations", "DRS (Formula One)",
    "Safety car (Formula One)", "Porpoising in Formula One",
    "Formula One car", "Formula One tyres",
    "Kinetic energy recovery system",
    "Ground effect (cars)",
    "Formula One pit stop",
    "Formula One World Constructors Championship",
]

# ── F1 Fandom wiki ─────────────────────────────────────────────────────────
# A separate community wiki with different editorial coverage from Wikipedia.
# Uses the standard MediaWiki API.
FANDOM_API = "https://f1.fandom.com/api.php"

FANDOM_ARTICLES = [
    "Lewis Hamilton",
    "Max Verstappen",
    "Ayrton Senna",
    "Michael Schumacher",
    "Fernando Alonso",
    "Sebastian Vettel",
    "Jenson Button",
    "Kimi Räikkönen",
    "Damon Hill",
    "Mika Häkkinen",
    "Nigel Mansell",
    "Alain Prost",
    "Niki Lauda",
    "Scuderia Ferrari",
    "McLaren",
    "Williams",
    "Red Bull Racing",
    "2008 Formula One season",
    "2003 Formula One season",
    "Suzuka Circuit",
    "Circuit de Monaco",
    "Bahrain International Circuit",
    "DRS",
    "KERS",
    "Safety car",
]


def fetch_fandom_article(title: str) -> str | None:
    """Fetch plain text of a fandom wiki article via the MediaWiki API."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": "1",
        "redirects": "1",
        "format": "json",
    }
    try:
        resp = requests.get(FANDOM_API, params=params, timeout=15,
                            headers={"User-Agent": "f1-rag-project/1.0"})
        resp.raise_for_status()
        pages = resp.json()["query"]["pages"]
        page = next(iter(pages.values()))
        if "missing" in page or "extract" not in page:
            return None
        return page["extract"].strip()
    except Exception as e:
        print(f"  fandom error for '{title}': {e}")
        return None


os.makedirs("data", exist_ok=True)

# ── Fetch Wikipedia ────────────────────────────────────────────────────────
print("=== Fetching Wikipedia articles ===")
wiki_saved = 0
for title in WIKI_ARTICLES:
    page = wiki.page(title)
    if not page.exists():
        print(f"  skip (not found): {title}")
        continue
    # No prefix — keeps backward compatibility with existing chunks_store and test set
    fname = title.replace(" ", "_").replace("/", "-") + ".txt"
    with open(f"data/{fname}", "w", encoding="utf-8") as f:
        f.write(page.text)
    print(f"  saved {fname}  ({len(page.text):,} chars)")
    wiki_saved += 1
    time.sleep(0.5)

# ── Fetch Fandom ───────────────────────────────────────────────────────────
print("\n=== Fetching F1 Fandom wiki articles ===")
fandom_saved = 0
for title in FANDOM_ARTICLES:
    text = fetch_fandom_article(title)
    if not text:
        print(f"  skip (not found): {title}")
        continue
    fname = "fandom_" + title.replace(" ", "_").replace("/", "-") + ".txt"
    with open(f"data/{fname}", "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  saved {fname}  ({len(text):,} chars)")
    fandom_saved += 1
    time.sleep(0.4)

total = len(os.listdir("data"))
print(f"\ndone — {wiki_saved} Wikipedia + {fandom_saved} Fandom = {total} files in data/")

# ── Write a source manifest ────────────────────────────────────────────────
manifest = {
    "sources": {
        "wikipedia": {
            "description": "English Wikipedia articles fetched via the wikipedia-api library",
            "count": wiki_saved,
            "articles": WIKI_ARTICLES,
        },
        "fandom": {
            "description": "F1 Fandom wiki articles fetched via the MediaWiki API (f1.fandom.com)",
            "count": fandom_saved,
            "articles": FANDOM_ARTICLES,
        }
    }
}
with open("data/sources_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print("wrote data/sources_manifest.json")
