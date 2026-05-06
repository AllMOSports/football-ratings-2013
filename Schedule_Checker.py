"""
MSHSAA Schedule Checker — 2013 Football Season
===============================================
Uses Selenium + headless Chrome to fully render each MSHSAA schedule page
(including JavaScript), then compares games against the existing scoreboard.
 
Only games where the opponent is also a ranked team (in classifications.json)
are flagged as missing.
 
Outputs
-------
mshsaa_missing_games.csv   – every unique missing game detected
mshsaa_school_ids.csv      – team-name to MSHSAA school ID map (for review)
 
Requirements
------------
    pip install selenium requests beautifulsoup4 pandas webdriver-manager
 
Usage
-----
    python mshsaa_schedule_checker.py
"""
 
import json
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup
 
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
 
# ── File paths ────────────────────────────────────────────────────────────────
TEAMS_FILE      = "classifications.json"
SCOREBOARD_FILE = "football_scoreboard_2013.csv"
OUTPUT_MISSING  = "mshsaa_missing_games.csv"
OUTPUT_IDS      = "mshsaa_school_ids.csv"
 
# alg=19 is the MSHSAA 11-Man Football activity code
SCHEDULE_URL = "https://www.mshsaa.org/MySchool/Schedule.aspx?s={sid}&alg=19&year=2013"
LISTING_URL  = "https://www.mshsaa.org/Schools/SchoolListing.aspx"
 
# Seconds to wait for JS table to appear on each page
JS_WAIT_TIMEOUT = 15
# Seconds to pause between page loads (be polite to the server)
REQUEST_DELAY   = 2.0
 
HEADERS = {"User-Agent": "Mozilla/5.0 (MSHSAA-ScheduleChecker/1.0)"}
 
 
# ─────────────────────────────────────────────────────────────────────────────
#  Utilities
# ─────────────────────────────────────────────────────────────────────────────
 
def normalize(name):
    name = str(name).strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[''`\u2018\u2019]", "", name)
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return re.sub(r"\s+", " ", name).strip()
 
 
def strip_suffix(norm_key):
    for suffix in (" junior high school", " high school"):
        if norm_key.endswith(suffix):
            return norm_key[: -len(suffix)].strip()
    return norm_key
 
 
# ─────────────────────────────────────────────────────────────────────────────
#  Data loading
# ─────────────────────────────────────────────────────────────────────────────
 
def load_ranked_teams(path):
    with open(path, "r") as f:
        data = json.load(f)
    df = pd.DataFrame(data["teams"])
    df = df.rename(columns={"school": "Team Name", "classification": "Class"})
    df["Team Name"] = df["Team Name"].astype(str).str.strip()
    df["norm"]      = df["Team Name"].apply(normalize)
    return df.reset_index(drop=True)
 
 
def load_scoreboard(path):
    """
    Returns:
      pair_games  - dict mapping frozenset({norm_a, norm_b}) ->
                    list of (parsed_date, home_score, away_score, norm_home, norm_away)
      df          - the raw scoreboard DataFrame
 
    Matching logic (see game_in_scoreboard) uses team names + scores so that
    two different games between the same pair (e.g. regular season AND playoff)
    are never collapsed into one.  Date is kept only as a tiebreaker fallback.
    """
    df = pd.read_csv(path)
    df = df[["Date", "Home Team", "Home Score", "Away Team", "Away Score"]].dropna(
        subset=["Home Team", "Away Team"]
    )
    df["Date"]       = df["Date"].astype(str).str.strip()
    df["norm_home"]  = df["Home Team"].apply(normalize)
    df["norm_away"]  = df["Away Team"].apply(normalize)
    df["Home Score"] = pd.to_numeric(df["Home Score"], errors="coerce")
    df["Away Score"] = pd.to_numeric(df["Away Score"], errors="coerce")
 
    pair_games = defaultdict(list)
    for _, row in df.iterrows():
        pair   = frozenset([row["norm_home"], row["norm_away"]])
        parsed = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                parsed = datetime.strptime(row["Date"], fmt)
                break
            except Exception:
                pass
        pair_games[pair].append((
            parsed,
            row["Home Score"],
            row["Away Score"],
            row["norm_home"],
            row["norm_away"],
        ))
    return pair_games, df
 
 
def game_in_scoreboard(team_norm, opp_norm, game_date_str, pair_games,
                       score_team=None, score_opp=None, window_days=7):
    """
    Returns True if the scoreboard already contains this specific game.
 
    Matching priority:
      1. Teams + scores match exactly  -> definite match, return True
      2. Teams match + date within window, but scores differ or unknown
         -> treat as a DIFFERENT game (regular season vs playoff), return False
         so the game is correctly flagged as missing if scores don't align.
 
    This prevents two games between the same pair (e.g. a regular-season game
    and a playoff rematch) from being incorrectly collapsed into one entry.
    """
    pair = frozenset([team_norm, opp_norm])
    if pair not in pair_games:
        return False
 
    gdate = None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            gdate = datetime.strptime(game_date_str, fmt)
            break
        except ValueError:
            pass
 
    for (sbdate, home_score, away_score, norm_home, norm_away) in pair_games[pair]:
        # Determine which score belongs to team_norm vs opp_norm
        if norm_home == team_norm:
            sb_team_score, sb_opp_score = home_score, away_score
        else:
            sb_team_score, sb_opp_score = away_score, home_score
 
        # Score-based match: if scores are known and match exactly, it's a duplicate
        if (score_team is not None and score_opp is not None
                and sb_team_score == score_team and sb_opp_score == score_opp):
            return True
 
    # No score match found — not in scoreboard
    return False
 
 
# ─────────────────────────────────────────────────────────────────────────────
#  Selenium browser setup
# ─────────────────────────────────────────────────────────────────────────────
 
def build_driver():
    """Return a headless Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (MSHSAA-ScheduleChecker/1.0)")
 
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    return driver
 
 
def get_rendered_html(driver, url):
    """
    Load the schedule page and return the fully-rendered HTML.
    We no longer need to click any tab because Varsity rows are identified
    directly by data-level="1" in parse_schedule_page — tab state is irrelevant.
    """
    driver.get(url)
    try:
        WebDriverWait(driver, JS_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.schedule"))
        )
    except Exception:
        pass  # proceed with whatever rendered
    return driver.page_source
 
 
# ─────────────────────────────────────────────────────────────────────────────
#  School-ID lookup  (uses plain requests — listing page is server-rendered)
# ─────────────────────────────────────────────────────────────────────────────
 
def fetch_school_id_map():
    print("Fetching MSHSAA school listing ...")
    session = requests.Session()
    session.headers.update(HEADERS)
    resp = session.get(LISTING_URL, timeout=30)
    resp.raise_for_status()
    soup   = BeautifulSoup(resp.text, "html.parser")
    id_map = {}
    for a in soup.select("a[href*='MySchool']"):
        m = re.search(r"[?&]s=(\d+)", a.get("href", ""))
        if not m:
            continue
        id_map[normalize(a.get_text(strip=True))] = int(m.group(1))
    print(f"  {len(id_map)} school entries found.")
    return id_map
 
 
def find_school_id(team_name, norm, id_map):
    stripped = {strip_suffix(k): v for k, v in id_map.items()}
 
    if norm in id_map:      return id_map[norm]
    if norm in stripped:    return stripped[norm]
 
    candidates = [(k, v) for k, v in stripped.items()
                  if k.startswith(norm) or norm in k]
    if len(candidates) == 1:
        return candidates[0][1]
 
    words = [w for w in norm.split() if len(w) > 3]
    if words:
        wm = [(k, v) for k, v in stripped.items() if all(w in k for w in words)]
        if len(wm) == 1:
            return wm[0][1]
    return None
 
 
# ─────────────────────────────────────────────────────────────────────────────
#  Schedule page parser
# ─────────────────────────────────────────────────────────────────────────────
 
def parse_schedule_page(html):
    """
    Parse ONLY Varsity game rows from the schedule table.
 
    The MSHSAA schedule page puts all levels (Varsity, JV, etc.) into a
    single table and uses a data-level attribute on each <tr> to distinguish
    them.  Clicking the tab only toggles CSS visibility — it does not remove
    rows from the DOM.  We therefore ignore tab state entirely and filter
    purely on data-level:
 
        data-level="1"  →  Varsity   ← the only rows we want
        data-level="2"  →  Junior Varsity
        (higher values would be Freshman, etc.)
 
    Rows with no data-level attribute are header/footer rows and are skipped
    by the existing date-format check.
    """
    if not html:
        return []
 
    soup  = BeautifulSoup(html, "html.parser")
    games = []
 
    # Locate the schedule div then the schedule table inside it
    schedule_div = soup.find("div", id="ctl00_contentMain_divSchedule")
    if not schedule_div:
        return games
 
    schedule_table = None
    for table in schedule_div.find_all("table"):
        header_text = table.get_text()
        if "Date" in header_text and "Opponent" in header_text and "Score" in header_text:
            schedule_table = table
            break
 
    if not schedule_table:
        return games
 
    # Column layout:
    # [0]=Special Designation  [1]=Date  [2]=Opponent  [3]=Outcome  [4]=Score  [5]=Matchup
    rows = schedule_table.find_all("tr")
    for tr in rows[1:]:   # skip header row
 
        # ── KEY FILTER: only process Varsity rows (data-level="1") ───────────
        data_level = tr.get("data-level")
        if data_level is None:
            continue          # header/footer rows have no data-level
        if data_level != "1":
            continue          # skip JV (2), Freshman (3), etc.
 
        cells = tr.find_all(["td", "th"])
        if len(cells) < 5:
            continue
 
        date_text  = cells[1].get_text(strip=True)
        opp_text   = cells[2].get_text(strip=True)
        score_text = cells[4].get_text(strip=True)
 
        # Must be a real date row
        if not re.match(r"^\d{1,2}/\d{1,2}", date_text):
            continue
        # Skip tournament rows
        if "Tournament" in opp_text or "Tournament" in tr.get_text():
            continue
 
        # Away games: "at" prefix attached with no space — e.g. "atAva(6-5)"
        home_away = "away" if opp_text.startswith("at") else "home"
 
        # Strip leading "at" and trailing win-loss record "(W-L)"
        opp_clean = re.sub(r"^at", "", opp_text).strip()
        opp_clean = re.sub(r"\(\d+-\d+\)\s*$", "", opp_clean).strip()
 
        score_match = re.search(r"(\d+)\s*[-\u2013]\s*(\d+)", score_text)
        score_team  = int(score_match.group(1)) if score_match else None
        score_opp   = int(score_match.group(2)) if score_match else None
 
        # Zero-pad month and day so strptime("%m/%d/%Y") always succeeds
        m = re.match(r"(\d{1,2})/(\d{1,2})", date_text)
        month = m.group(1).zfill(2)
        day   = m.group(2).zfill(2)
 
        games.append({
            "date":          f"{month}/{day}/2013",
            "opponent":      opp_clean,
            "opponent_norm": normalize(opp_clean),
            "home_away":     home_away,
            "score_team":    score_team,
            "score_opp":     score_opp,
        })
    return games
 
 
def opponent_in_rankings(opp_norm, ranked_norms):
    """Exact normalized match only — opponent must be in classifications.json."""
    return opp_norm in ranked_norms
 
 
# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
 
def main():
    print("Loading ranked teams ...")
    teams_df     = load_ranked_teams(TEAMS_FILE)
    ranked_norms = set(teams_df["norm"].tolist())
    print(f"  {len(teams_df)} ranked teams.")
 
    print("Loading existing scoreboard ...")
    pair_games, _ = load_scoreboard(SCOREBOARD_FILE)
    print(f"  {len(pair_games)} unique team pairs in scoreboard.")
 
    id_map = fetch_school_id_map()
 
    teams_df["school_id"] = None
    teams_df["id_found"]  = False
    for idx, row in teams_df.iterrows():
        sid = find_school_id(row["Team Name"], row["norm"], id_map)
        teams_df.at[idx, "school_id"] = sid
        teams_df.at[idx, "id_found"]  = sid is not None
 
    teams_df[["Team Name", "Class", "district", "school_id", "id_found"]].to_csv(OUTPUT_IDS, index=False)
 
    n_found = int(teams_df["id_found"].sum())
    print(f"\nSchool IDs resolved: {n_found}/{len(teams_df)}")
    for nm in teams_df[~teams_df["id_found"]]["Team Name"].tolist():
        print(f"  No ID found: {nm}")
 
    print("\nStarting headless browser ...")
    driver = build_driver()
 
    missing_rows  = []
    teams_with_id = teams_df[teams_df["id_found"]].copy()
    total         = len(teams_with_id)
 
    try:
        for i, (_, team_row) in enumerate(teams_with_id.iterrows(), 1):
            team_name = team_row["Team Name"]
            team_norm = team_row["norm"]
            sid       = int(team_row["school_id"])
            url       = SCHEDULE_URL.format(sid=sid)
 
            print(f"\n[{i}/{total}] {team_name}  (ID={sid})")
            try:
                html = get_rendered_html(driver, url)
            except Exception as exc:
                print(f"  WARNING: Skipped — {exc}")
                time.sleep(REQUEST_DELAY)
                continue
 
            games = parse_schedule_page(html)
            time.sleep(REQUEST_DELAY)
 
            if not games:
                print("  (no Varsity game rows parsed)")
                continue
 
            print(f"  {len(games)} Varsity games on MSHSAA page.")
            for game in games:
                opp_norm = game["opponent_norm"]
                if not opponent_in_rankings(opp_norm, ranked_norms):
                    continue
 
                if not game_in_scoreboard(team_norm, opp_norm, game["date"], pair_games,
                                          score_team=game["score_team"], score_opp=game["score_opp"]):
                    print(f"  MISSING: {game['date']}  vs  {game['opponent']}"
                          f"  ({game['home_away']})  {game['score_team']}-{game['score_opp']}")
                    missing_rows.append({
                        "Ranked Team":    team_name,
                        "Team School ID": sid,
                        "Date":           game["date"],
                        "Opponent":       game["opponent"],
                        "Opponent Norm":  opp_norm,
                        "Home/Away":      game["home_away"],
                        "Team Score":     game["score_team"],
                        "Opp Score":      game["score_opp"],
                        "MSHSAA URL":     url,
                    })
                else:
                    print(f"  OK: {game['date']}  vs  {game['opponent']}")
 
    finally:
        driver.quit()
 
    print(f"\n{'='*60}")
    if missing_rows:
        missing_df = pd.DataFrame(missing_rows)
        missing_df["_key"] = missing_df.apply(
            lambda r: str(frozenset([normalize(r["Ranked Team"]), r["Opponent Norm"], r["Date"]])),
            axis=1,
        )
        missing_df = (missing_df
                      .drop_duplicates(subset="_key")
                      .drop(columns=["_key", "Opponent Norm"])
                      .reset_index(drop=True))
        missing_df.to_csv(OUTPUT_MISSING, index=False)
        print(f"Done. {len(missing_df)} unique missing games -> {OUTPUT_MISSING}")
    else:
        # Always write the file so the GitHub Actions artifact upload doesn't fail
        pd.DataFrame(columns=["Ranked Team", "Team School ID", "Date", "Opponent",
                               "Home/Away", "Team Score", "Opp Score", "MSHSAA URL"]
                     ).to_csv(OUTPUT_MISSING, index=False)
        print("No missing games detected.")
 
    print(f"School ID map -> {OUTPUT_IDS}")
 
 
if __name__ == "__main__":
    main()
