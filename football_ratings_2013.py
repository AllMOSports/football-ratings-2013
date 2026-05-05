import requests
from bs4 import BeautifulSoup
import json
import csv
import re
import pandas as pd
from datetime import datetime, date, timedelta
import time
 
# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
 
SEASON_START  = date(2013, 8, 1)
SEASON_END    = date(2013, 12, 15)
BASE_URL      = "https://www.mshsaa.org/activities/scoreboard.aspx?alg=19&date={}"
MAX_POINTS    = 100
OUTPUT_PATH   = "football_ratings_2013.json"
CSV_PATH      = "football_scoreboard_2013.csv"
CLASSIFICATIONS_PATH  = "classifications.json"
SCHOOLS_CSV           = "mshsaa_schools.csv"
ITERATIONS            = 1000
LEARNING_RATE         = 0.1
COMPETITIVE_THRESHOLD = 40
 
# ---------------------------------------------------------------------------
# MANUAL GAMES (not listed on MSHSAA Scoreboard)
# ---------------------------------------------------------------------------
# Add any games missing from the MSHSAA scoreboard here.
# Format: ("YYYY-MM-DD", "Team 1 Name", score1, "Team 2 Name", score2)
# Team names must match exactly the names in classifications.json.
 
MANUAL_GAMES = [
    ("2013-08-30", "Chaffee", 58, "Grandview (Hillsboro)", 15),
    ("2013-09-20", "Portageville", 7, "Chaffee", 38),
    ("2013-10-25", "Crystal City", 28, "Grandview (Hillsboro)", 0),
    ("2013-08-30", "Hayti", 7, "Thayer", 16),
    ("2013-09-27", "Portageville", 18, "Hayti", 12),
    ("2013-10-04", "Malden", 53, "Hayti", 14),
    ("2013-08-30", "Portageville", 39, "St. Pius X (Festus)", 21),
    ("2013-09-06", "Kennett", 26, "Portageville", 6),
    ("2013-09-13", "Malden", 32, "Portageville", 19),
    ("2013-10-11", "Portageville", 53, "East Prairie", 0),
    ("2013-10-18", "Grandview (Hillsboro)", 0, "St. Vincent", 63),
    ("2013-09-13", "Thayer", 14, "Liberty (Mountain View)", 53),
    ("2013-10-04", "Cabool", 27, "Thayer", 58),
    ("2013-10-11", "Ava", 0, "Thayer", 8),
    ("2013-10-25", "Mountain Grove", 14, "Thayer", 0),
    ("2013-09-27", "Grandview (Hillsboro)", 0, "Valle Catholic", 48),
    ("2013-08-30", "Lockwood with Golden City", 28, "Greenfield", 20),
    ("2013-09-06", "Greenfield", 19, "Pierce City", 6),
    ("2013-09-13", "Greenfield", 12, "Jasper", 26),
    ("2013-09-20", "Archie", 20, "Greenfield", 35),
    ("2013-09-27", "Greenfield", 15, "Liberal with Bronaugh", 6),
    ("2013-10-04", "Sarcoxie", 31, "Greenfield", 8),
    ("2013-10-11", "Greenfield", 14, "Diamond", 32),
    ("2013-10-18", "Miller", 6, "Greenfield", 2),
    ("2013-10-25", "McAuley Catholic", 22, "Greenfield", 6),
    ("2013-09-20", "Jasper", 41, "Lockwood with Golden City", 14),
    ("2013-10-11", "Jasper", 35, "Miller", 0),
    ("2013-08-30", "Miller", 7, "Marionville", 46),
    ("2013-09-20", "Marionville", 23, "Ash Grove", 31),
    ("2013-10-11", "Fair Grove", 14, "Marionville", 49),
    ("2013-10-18", "Skyline", 26, "Marionville", 40),
    ("2013-09-27", "Ash Grove", 54, "McAuley Catholic", 14),
    ("2013-10-04", "Diamond", 26, "McAuley Catholic", 6),
    ("2013-10-11", "Lockwood with Golden City", 22, "McAuley Catholic", 39),
    ("2013-09-06", "Liberal with Bronaugh", 6, "Miller", 28),
    ("2013-09-20", "Miller", 14, "Diamond", 53),
    ("2013-10-04", "Miller", 33, "Pierce City", 26),
    ("2013-10-25", "Miller", 35, "Sarcoxie", 42),
    ("2013-10-11", "Adrian", 18, "Osceola", 63),
    ("2013-10-04", "Osceola", 63, "Archie", 20),
    ("2013-09-06", "Osceola", 59, "Appleton City with Montrose", 22),
    ("2013-09-13", "Osceola", 36, "Lexington", 21),
    ("2013-09-20", "Drexel with Miami (Amoret)", 14, "Osceola", 37),
    ("2013-10-18", "Cole Camp", 6, "Osceola", 46),
    ("2013-10-04", "Ash Grove", 49, "Skyline", 28),
    ("2013-10-04", "Wellington-Napoleon", 42, "Concordia", 68),
    ("2013-10-25", "Trenton", 27, "Concordia", 44),
    ("2013-09-13", "Wellington-Napoleon", 50, "Santa Fe", 44),
    ("2013-09-20", "Knox County", 38, "Paris", 44),
    ("2013-10-18", "Knox County", 36, "Schuyler County", 14),
    ("2013-10-25", "North Shelby", 6, "Knox County", 32),
    ("2013-08-30", "South Shelby", 23, "Louisiana", 20),
    ("2013-09-20", "Louisiana", 14, "Mark Twain", 12),
    ("2013-10-04", "Macon", 40, "Louisiana", 8),
    ("2013-10-18", "Louisiana", 22, "Centralia", 55),
    ("2013-08-30", "North Shelby", 0, "Westran", 48),
    ("2013-09-06", "North Shelby", 20, "Fayette", 38),
    ("2013-09-13", "Paris", 48, "North Shelby", 0),
    ("2013-09-20", "Salisbury", 57, "North Shelby", 0),
    ("2013-09-27", "Scotland County", 34, "North Shelby", 12),
    ("2013-10-04", "North Shelby", 28, "Schuyler County", 36),
    ("2013-10-11", "North Shelby", 12, "Putnam County", 46),
    ("2013-09-06", "Schuyler County", 0, "Marceline", 50),
    ("2013-10-11", "Schuyler County", 0, "Milan", 42),
    ("2013-10-25", "Schuyler County", 6, "Scotland County", 47),
    ("2013-10-18", "Scotland County", 14, "Putnam County", 20),
    ("2013-09-06", "Macon", 25, "South Shelby", 14),
    ("2013-09-13", "South Shelby", 14, "Palmyra", 56),
    ("2013-09-20", "Centralia", 50, "South Shelby", 0),
    ("2013-09-27", "South Shelby", 27, "Monroe City", 0),
    ("2013-10-04", "South Shelby", 8, "Brookfield", 14),
    ("2013-10-11", "Highland", 6, "South Shelby", 46),
    ("2013-10-18", "Clark County", 7, "South Shelby", 35),
    ("2013-10-25", "South Shelby", 41, "Mark Twain", 0),
    ("2013-09-13", "Brookfield", 16, "Marceline", 14),
    ("2013-09-06", "Albany", 26, "Milan", 48),
    ("2013-09-13", "Putnam County", 0, "Trenton", 19),
    ("2013-10-11", "West Platte", 14, "Mid-Buchanan", 27),
    ("2013-09-27", "North Platte", 16, "West Platte", 35),
    ("2013-10-04", "Lathrop", 59, "North Platte", 8),
    ("2013-10-11", "North Platte", 9, "East Buchanan", 44),
    ("2013-10-18", "Orrick", 6, "Wellington-Napoleon", 46),
    ("2013-09-06", "Wellington-Napoleon", 0, "West Platte", 35),
    ("2013-09-20", "Lexington", 47, "Wellington-Napoleon", 6),
    ("2013-10-11", "St. Paul Lutheran (Concordia)", 50, "Wellington-Napoleon", 12),
    ("2013-10-25", "Wellington-Napoleon", 34, "Sweet Springs with Malta Bend", 0),
    ("2013-09-13", "West Platte", 45, "East Buchanan", 48),
    ("2013-09-20", "West Platte", 16, "Lathrop", 39),
    ("2013-10-04", "West Platte", 31, "Penney", 39),
    ("2013-10-18", "Plattsburg", 18, "West Platte", 14),
    ("2013-10-25", "Lawson", 42, "West Platte", 12),
    ("2013-09-20", "Albany", 7, "Maysville", 14),
    ("2013-10-11", "Albany", 0, "South Harrison", 68),
    ("2013-10-18", "Albany", 14, "Gallatin", 28),
    ("2013-09-20", "East Buchanan", 46, "Plattsburg", 12),
    ("2013-10-18", "East Buchanan", 42, "Lathrop", 66),
    ("2013-09-13", "Lathrop", 37, "Penney", 15),
    ("2013-08-30", "Van Horn", 27, "Polo", 7),
    ("2013-09-06", "Polo", 8, "Lathrop", 47),
    ("2013-10-04", "Charleston", 40, "Kennett", 20),
    ("2013-09-06", "Grandview (Hillsboro)", 8, "East Prairie", 43),
    ("2013-09-13", "Grandview (Hillsboro)", 0, "St. Pius X (Festus)", 44),
    ("2013-09-20", "Grandview (Hillsboro)", 29, "Missouri Military Academy", 22),
    ("2013-10-04", "Herculaneum", 40, "Grandview (Hillsboro)", 18),
    ("2013-10-11", "Jefferson (Festus)", 57, "Grandview (Hillsboro)", 22),
    ("2013-10-18", "Malden", 54, "Kennett", 25),
    ("2013-09-13", "Cuba", 32, "Houston", 24),
    ("2013-10-18", "Fair Grove", 7, "Ash Grove", 43),
    ("2013-10-25", "Fair Grove", 18, "Hollister", 38),
    ("2013-08-30", "Houston", 16, "Salem", 48),
    ("2013-10-11", "Willow Springs", 61, "Houston", 16),
    ("2013-10-18", "Houston", 22, "Mountain Grove", 56),
    ("2013-10-25", "Liberty (Mountain View)", 66, "Houston", 0),
    ("2013-09-20", "Liberty (Mountain View)", 47, "Ava", 13),
    ("2013-10-04", "Mountain Grove", 34, "Liberty (Mountain View)", 57),
    ("2013-10-11", "Cabool", 25, "Liberty (Mountain View)", 59),
    ("2013-08-30", "Logan-Rogersville", 0, "Mountain Grove", 38),
    ("2013-09-13", "Mountain Grove", 33, "Ava", 20),
    ("2013-09-27", "Mountain Grove", 55, "Cabool", 0),
    ("2013-10-11", "Ash Grove", 42, "Pleasant Hope", 0),
    ("2013-10-25", "Ash Grove", 21, "Strafford", 37),
    ("2013-08-30", "Cabool", 25, "Ash Grove", 57),
    ("2013-09-20", "Butler", 7, "Van Horn", 49),
    ("2013-09-06", "Sarcoxie", 54, "Diamond", 28),
    ("2013-09-13", "Lockwood with Golden City", 20, "Sarcoxie", 27),
    ("2013-10-25", "Bowling Green", 0, "Central (Park Hills)", 52),
    ("2013-09-20", "Macon", 41, "Clark County", 27),
    ("2013-09-27", "Clark County", 35, "Mark Twain", 8),
    ("2013-10-11", "Clark County", 6, "Centralia", 49),
    ("2013-10-25", "Brookfield", 42, "Clark County", 6),
    ("2013-08-30", "Centralia", 55, "Highland", 0),
    ("2013-09-06", "Highland", 14, "Brookfield", 17),
    ("2013-09-27", "Highland", 8, "Macon", 40),
    ("2013-08-30", "Brookfield", 35, "Mark Twain", 0),
    ("2013-09-06", "Mark Twain", 30, "Monroe City", 50),
    ("2013-09-13", "Mark Twain", 8, "Centralia", 54),
    ("2013-09-20", "Monroe City", 6, "Brookfield", 9),
    ("2013-10-04", "Centralia", 48, "Monroe City", 6),
    ("2013-09-06", "Palmyra", 24, "Centralia", 21),
    ("2013-10-11", "Brookfield", 7, "Palmyra", 35),
    ("2013-09-20", "Blair Oaks", 48, "Southern Boone", 0),
    ("2013-10-25", "Blair Oaks", 48, "Eldon", 12),
    ("2013-09-27", "Hermann", 66, "Owensville", 21),
    ("2013-10-11", "Hermann", 26, "St. Clair", 22),
    ("2013-09-27", "Holden", 62, "Lexington", 38),
    ("2013-09-13", "O'Hara", 42, "Knob Noster", 14),
    ("2013-10-04", "Lexington", 43, "Knob Noster", 13),
    ("2013-10-18", "Richmond", 49, "Knob Noster", 0),
    ("2013-09-13", "Sherwood", 15, "Van Horn", 33),
    ("2013-10-11", "Southeast", 40, "Southwest Early College", 0),
    ("2013-09-06", "Bishop LeBlond", 69, "East (Kansas City)", 6),
    ("2013-09-27", "Brookfield", 9, "Centralia", 21),
    ("2013-10-18", "Macon", 12, "Brookfield", 7),
    ("2013-08-30", "Trenton", 28, "Carrollton", 14),
    ("2013-09-20", "Carrollton", 41, "East (Kansas City)", 6),
    ("2013-10-11", "Lexington", 28, "Carrollton", 12),
    ("2013-09-27", "Lawson", 28, "Lathrop", 14),
    ("2013-10-11", "Lathrop", 51, "Plattsburg", 27),
    ("2013-08-30", "Lexington", 14, "Oak Grove", 40),
    ("2013-09-06", "Lexington", 14, "Trenton", 27),
    ("2013-10-18", "Lafayette County", 55, "Lexington", 6),
    ("2013-10-25", "Richmond", 42, "Lexington", 20),
    ("2013-08-30", "Plattsburg", 24, "Northeast (Kansas City)", 0),
    ("2013-09-20", "Trenton", 7, "Lafayette County", 46),
    ("2013-09-27", "Pembroke Hill", 33, "Trenton", 13),
    ("2013-10-18", "Kirksville", 48, "Trenton", 14),
    ("2013-09-13", "Kennett", 21, "Central (New Madrid County)", 40),
    ("2013-08-30", "Sullivan", 0, "Central (Park Hills)", 3),
    ("2013-09-06", "North County", 7, "Central (Park Hills)", 34),
    ("2013-09-13", "Central (Park Hills)", 25, "Fredericktown", 0),
    ("2013-09-27", "Ste. Genevieve", 14, "Central (Park Hills)", 17),
    ("2013-10-04", "Central (Park Hills)", 34, "Potosi", 0),
    ("2013-10-11", "Central (Park Hills)", 41, "Perryville", 0),
    ("2013-10-18", "Central (Park Hills)", 39, "Dexter", 0),
    ("2013-09-27", "Kennett", 15, "Dexter", 27),
    ("2013-08-30", "Fredericktown", 27, "Kennett", 20),
    ("2013-09-06", "Hillsboro", 28, "Fredericktown", 14),
    ("2013-10-25", "North County", 41, "Fredericktown", 14),
    ("2013-10-18", "Potosi", 27, "North County", 28),
    ("2013-10-25", "DeSoto with Kingston", 13, "Potosi", 34),
    ("2013-10-18", "DeSoto with Kingston", 21, "Ste. Genevieve", 49),
    ("2013-08-30", "Owensville", 6, "St. Francis Borgia", 26),
    ("2013-10-11", "Union", 49, "Owensville", 14),
    ("2013-10-25", "Owensville", 21, "St. Clair", 34),
    ("2013-09-06", "Ava", 40, "Logan-Rogersville", 3),
    ("2013-10-18", "Ava", 48, "Cabool", 6),
    ("2013-09-13", "Springfield Catholic", 14, "Logan-Rogersville", 41),
    ("2013-09-20", "Logan-Rogersville", 23, "Marshfield", 50),
    ("2013-09-27", "Reeds Spring", 34, "Logan-Rogersville", 14),
    ("2013-10-04", "Logan-Rogersville", 0, "Aurora", 35),
    ("2013-10-11", "Bolivar", 35, "Logan-Rogersville", 0),
    ("2013-10-18", "Logan-Rogersville", 29, "Hollister", 26),
    ("2013-09-27", "Monett", 26, "Aurora", 21),
    ("2013-10-18", "Cassville", 21, "Aurora", 0),
    ("2013-09-06", "Cassville", 45, "McDonald County", 7),
    ("2013-09-20", "Cassville", 7, "Seneca", 26),
    ("2013-09-27", "Carl Junction", 49, "Cassville", 14),
    ("2013-10-04", "Cassville", 27, "Monett", 0),
    ("2013-10-11", "East Newton", 6, "Cassville", 43),
    ("2013-09-20", "East Newton", 0, "Monett", 34),
    ("2013-09-27", "East Newton", 13, "Mt. Vernon", 32),
    ("2013-10-25", "East Newton", 0, "Seneca", 44),
    ("2013-09-20", "Bolivar", 48, "Hollister", 0),
    ("2013-08-30", "Monett", 28, "Mt. Vernon", 14),
    ("2013-09-06", "Neosho", 25, "Monett", 28),
    ("2013-09-13", "Monett", 42, "McDonald County", 0),
    ("2013-10-18", "Seneca", 27, "Monett", 0),
    ("2013-10-25", "Monett", 6, "Carl Junction", 49),
    ("2013-08-30", "Duchesne", 26, "Hillsboro", 6),
    ("2013-10-25", "Centralia", 49, "Macon", 14),
    ("2013-09-13", "Chillicothe", 7, "Maryville", 32),
    ("2013-10-25", "Chillicothe", 35, "Benton", 20),
    ("2013-10-04", "Center", 35, "Warrensburg", 2),
    ("2013-10-11", "O'Hara", 10, "Center", 35),
    ("2013-09-27", "Clinton", 7, "O'Hara", 27),
    ("2013-10-18", "Warrensburg", 13, "Clinton", 20),
    ("2013-10-18", "Oak Grove", 49, "Grain Valley", 22),
    ("2013-10-25", "Grain Valley", 42, "Odessa", 13),
    ("2013-10-04", "Southwest Early College", 6, "Pembroke Hill", 41),
    ("2013-09-06", "St. Pius X (Kansas City)", 0, "Maryville", 46),
    ("2013-10-04", "Benton", 6, "Maryville", 36),
    ("2013-10-04", "Nevada", 46, "Northeast (Kansas City)", 0),
    ("2013-08-30", "O'Hara", 36, "Richmond", 42),
    ("2013-09-13", "Richmond", 23, "Excelsior Springs", 20),
    ("2013-10-11", "Warrensburg", 13, "St. Pius X (Kansas City)", 35),
    ("2013-10-18", "St. Pius X (Kansas City)", 21, "O'Hara", 20),
    ("2013-09-27", "Farmington", 29, "North County", 56),
    ("2013-09-20", "DeSoto with Kingston", 0, "Festus", 37),
    ("2013-09-27", "Festus", 36, "Hillsboro", 50),
    ("2013-10-04", "North County", 20, "Festus", 42),
    ("2013-09-20", "North County", 55, "Hillsboro", 33),
    ("2013-10-04", "Hillsboro", 60, "Windsor (Imperial)", 0),
    ("2013-10-11", "Hillsboro", 48, "DeSoto with Kingston", 13),
    ("2013-10-18", "Lutheran South", 42, "Hillsboro", 76),
    ("2013-09-13", "DeSoto with Kingston", 33, "North County", 53),
    ("2013-10-11", "Windsor (Imperial)", 14, "North County", 21),
    ("2013-09-27", "Windsor (Imperial)", 8, "DeSoto with Kingston", 26),
    ("2013-08-30", "St. Clair", 15, "Washington", 24),
    ("2013-09-06", "St. Clair", 32, "DeSoto with Kingston", 22),
    ("2013-09-27", "St. Clair", 21, "Union", 49),
    ("2013-10-18", "St. Francis Borgia", 39, "St. Clair", 34),
    ("2013-10-04", "DeSoto with Kingston", 6, "Union", 46),
    ("2013-10-18", "Ozark", 0, "Webb City", 59),
    ("2013-10-18", "Poplar Bluff", 42, "Normandy Collaborative", 14),
    ("2013-09-20", "Helias Catholic", 17, "Hickman", 27),
    ("2013-09-06", "Grain Valley", 23, "Benton", 17),
    ("2013-09-13", "Warrensburg", 6, "Grain Valley", 47),
    ("2013-09-20", "Grain Valley", 37, "Smith-Cotton", 14),
    ("2013-09-06", "William Chrisman", 27, "Grandview", 48),
    ("2013-09-20", "Warrensburg", 0, "Harrisonville", 48),
    ("2013-09-06", "Pleasant Hill", 44, "Warrensburg", 0),
    ("2013-08-30", "Warrensburg", 7, "Excelsior Springs", 33),
    ("2013-09-27", "Smith-Cotton", 42, "Warrensburg", 6),
    ("2013-10-25", "O'Hara", 47, "Warrensburg", 28),
    ("2013-08-30", "Platte County", 42, "William Chrisman", 7),
    ("2013-10-18", "Jackson", 27, "Hickman", 34),
    ("2013-09-27", "Christian Brothers College", 27, "Vianney", 7),
    ("2013-10-04", "Chaminade College Preparatory", 19, "Christian Brothers College", 47),
    ("2013-10-05", "McCluer North", 31, "Hazelwood East", 30),
    ("2013-09-06", "Holt", 15, "Hickman", 30),
    ("2013-10-04", "Smith-Cotton", 36, "O'Hara", 43),
    ("2013-10-25", "Neosho", 20, "Ozark", 41),
    ("2013-10-11", "Nixa", 45, "Ozark", 7),
    ("2013-09-27", "Ozark", 24, "Willard", 55),
    ("2013-10-11", "Fort Osage", 56, "William Chrisman", 0),
    ("2013-10-18", "William Chrisman", 19, "Truman", 13),
    ("2013-10-18", "Central (St. Joseph)", 48, "Park Hill", 20),
    ("2013-09-13", "Park Hill", 26, "Lee's Summit", 31),
    ("2013-09-20", "Christian Brothers College", 49, "Lindbergh", 29),
    ("2013-10-11", "Christian Brothers College", 14, "De Smet Jesuit", 11),
    ("2013-10-25", "Francis Howell", 12, "Christian Brothers College", 30),
    ("2013-08-30", "Hickman", 16, "Lee's Summit North", 27),
    ("2013-10-04", "Hickman", 33, "Jefferson City", 40),
    ("2013-10-25", "Hickman", 6, "Rockhurst", 21),
]
 
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.mshsaa.org/"
}
 
# ---------------------------------------------------------------------------
# CLASSIFICATIONS
# ---------------------------------------------------------------------------
 
def load_classifications(path=CLASSIFICATIONS_PATH):
    """Return team_to_class and team_to_district dicts keyed by school name."""
    with open(path) as f:
        data = json.load(f)
    team_to_class    = {}
    team_to_district = {}
    for entry in data["teams"]:
        school = entry["school"]
        team_to_class[school]    = entry["classification"]
        team_to_district[school] = entry["district"]
    return team_to_class, team_to_district
 
 
# ---------------------------------------------------------------------------
# NAME RESOLUTION
# ---------------------------------------------------------------------------
 
def build_id_to_classname(team_to_class, schools_csv=SCHOOLS_CSV):
    """
    Build { school_id_str : classification_name } by exact-matching
    mshsaa_schools.csv names to classifications.json names after stripping
    the ' High School' suffix. No fuzzy matching used.
 
    MANUAL_OVERRIDES covers the 21 schools whose mshsaa_schools.csv name
    does not match their classifications.json name. IDs were looked up
    directly from the MSHSAA scoreboard pages.
    """
    MANUAL_OVERRIDES = {
        "271": "Clopton with Elsberry",
        "331": "King City with Pattonsburg",
        "126": "Lockwood with Golden City",
        "421": "Princeton with Mercer",
        "424": "Rich Hill with Hume",
        "431": "Salisbury",
        "435": "Scott City",
        "443": "Skyline",
        "193": "Slater",
        "194": "Smith-Cotton",
        "197": "South Callaway",
        "549": "St. Mary's South Side",
        "463": "Stockton",
        "207": "Sullivan",
        "208": "Sumner",
        "469": "Sweet Springs with Malta Bend",
        "198": "Truman",
        "479": "University Academy Charter",
        "204": "Van Horn",
        "206": "Vashon",
        "20": "Appleton City with Montrose",
        "275": "Drexel with Miami (Amoret)",
        "575": "Renaissance Academy Charter",
        "172": "St. James",
        "35": "DeSoto with Kingston",
        "917": "Father Tolton with Calvary Lutheran",
        "342": "Liberal with Bronaugh",
        "776": "Transportation and Law with Beaumont",
        "483": "Van-Far with Community",
    }
 
    df = pd.read_csv(schools_csv)
    known_class_names = set(team_to_class.keys())
 
    id_to_classname = {}
    for _, row in df.iterrows():
        full_name = row["school_name"]
        sid       = str(row["school_id"])
        stripped  = full_name.replace(" High School", "").strip()
 
        if stripped in known_class_names:
            id_to_classname[sid] = stripped
        elif full_name in known_class_names:
            id_to_classname[sid] = full_name
 
    # Apply manual overrides last so they always take priority
    id_to_classname.update(MANUAL_OVERRIDES)
 
    print(f"  [name-resolve] {len(id_to_classname)} schools mapped by ID "
          f"({len(MANUAL_OVERRIDES)} via manual overrides)")
    return id_to_classname
 
 
def resolve_name(cell, id_to_classname, known_teams):
    """
    Resolve a scoreboard table cell to a classification name.
 
    Step 1: Extract s= ID from href → look up in id_to_classname.
            Handles renamed/merged schools (e.g. 'Scott City with Chaffee'
            → 'Scott City') because the ID in the href never changes.
    Step 2: Exact match of display text against known_teams.
            Handles co-op names that exist in classifications as-is.
    Returns None if unresolvable — game will be skipped.
    """
    a = cell.find("a", href=lambda h: h and "/MySchool/Schedule.aspx" in h)
    if not a:
        return None
 
    # Step 1: ID-based lookup
    href  = a.get("href", "")
    match = re.search(r"[?&]s=(\d+)", href, re.IGNORECASE)
    if match:
        sid = match.group(1)
        if sid in id_to_classname:
            return id_to_classname[sid]
 
    # Step 2: Exact display text match
    display_text = a.get_text(strip=True)
    if display_text in known_teams:
        return display_text
 
    return None
 
 
# ---------------------------------------------------------------------------
# SCRAPING
# ---------------------------------------------------------------------------
 
def is_mshsaa_team(cell):
    return cell.find(
        "a", href=lambda h: h and "/MySchool/Schedule.aspx" in h
    ) is not None
 
 
def parse_score(text):
    text = text.strip()
    if not text:
        return None
    try:
        score = int(text)
    except ValueError:
        return None
    return score if 0 <= score <= MAX_POINTS else None
 
 
def is_forfeit(c1, c2):
    return "forfeit" in (c1.get_text() + c2.get_text()).lower()
 
 
def scrape_date(target_date, id_to_classname, known_teams):
    url = BASE_URL.format(target_date.strftime("%m%d%Y"))
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Failed {target_date}: {e}")
        return []
 
    soup  = BeautifulSoup(resp.text, "html.parser")
    games = []
 
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue
        if "final" not in rows[-1].get_text().lower():
            continue
 
        t1c = rows[1].find_all("td")
        t2c = rows[2].find_all("td")
        if len(t1c) < 3 or len(t2c) < 3:
            continue
        if not is_mshsaa_team(t1c[1]) or not is_mshsaa_team(t2c[1]):
            continue
        if is_forfeit(t1c[1], t2c[1]):
            continue
 
        name1 = resolve_name(t1c[1], id_to_classname, known_teams)
        name2 = resolve_name(t2c[1], id_to_classname, known_teams)
 
        if name1 is None or name2 is None:
            continue
 
        s1 = parse_score(t1c[2].get_text())
        s2 = parse_score(t2c[2].get_text())
        if s1 is None or s2 is None:
            continue
 
        games.append((
            target_date.strftime("%Y-%m-%d"),
            name1, s1,
            name2, s2
        ))
 
    return games
 
 
def scrape_full_season(id_to_classname, known_teams):
    all_games = []
    current   = SEASON_START
    while current <= min(SEASON_END, date.today()):
        print(f"  Scraping {current}...", end=" ", flush=True)
        day_games = scrape_date(current, id_to_classname, known_teams)
        all_games.extend(day_games)
        print(f"{len(day_games)} games")
        current += timedelta(days=1)
        time.sleep(0.5)
    return all_games
 
 
def deduplicate_games(all_games):
    """
    Remove duplicate games where the same two teams played on the same date
    with the same scores, regardless of which team is listed as home or away.
 
    A game is considered a duplicate if another game exists with:
      - The same date
      - The same two team names (in either order)
      - The same two scores (in either order)
 
    The key is built from a frozenset of (team, score) pairs so that
    (Date, Team A, 54, Team B, 13) and (Date, Team B, 13, Team A, 54)
    produce the same key and only one is kept.
    """
    seen         = set()
    unique_games = []
    duplicates   = 0
 
    for game in all_games:
        date_str, t1, s1, t2, s2 = game
        # Key is date + frozenset of team names only — order independent.
        # Scores are intentionally excluded so that (Team A home, Team B away)
        # and (Team B home, Team A away) on the same date are always treated
        # as the same game regardless of which score appears first.
        key = (date_str, frozenset([t1, t2]))
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique_games.append(game)
 
    if duplicates:
        print(f"  Removed {duplicates} duplicate game(s). "
              f"{len(unique_games)} unique games remain.")
    else:
        print(f"  No duplicates found. {len(unique_games)} games.")
 
    return unique_games
 
 
def report_missing_teams(all_games, team_to_class):
    """
    After scraping is complete, compare every team in classifications.json
    against the teams that actually appeared in scraped games.
    Print only the teams that have zero games — these are the ones that
    genuinely need attention (either their ID needs adding or their
    classifications.json name needs correcting).
    """
    teams_with_games = set()
    for _, t1, _, t2, _ in all_games:
        teams_with_games.add(t1)
        teams_with_games.add(t2)
 
    missing = sorted(
        t for t in team_to_class if t not in teams_with_games
    )
 
    if missing:
        print(f"\n  MISSING TEAMS: {len(missing)} classification schools have "
              f"no games in the scraped data.")
        print(f"  These teams need attention — either their MSHSAA page shows")
        print(f"  a different name than classifications.json, or they did not")
        print(f"  play any games this season.")
        print(f"  Missing: {missing}\n")
    else:
        print("\n  All classification schools have at least one game. \n")
 
 
# ---------------------------------------------------------------------------
# CSV OUTPUT
# ---------------------------------------------------------------------------
 
def save_csv(all_games):
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Home Team", "Home Score", "Away Team", "Away Score"])
        for date_str, t1, s1, t2, s2 in all_games:
            writer.writerow([date_str, t1, s1, t2, s2])
    print(f"Saved {len(all_games)} games to {CSV_PATH}")
 
 
# ---------------------------------------------------------------------------
# RATING ENGINE
# ---------------------------------------------------------------------------
 
def run_iterations(games, teams, off_rating, def_rating, league_avg,
                   iterations, phase_label, ovr_filter=None):
    for iteration in range(iterations):
        off_error    = {t: 0.0 for t in teams}
        def_error    = {t: 0.0 for t in teams}
        games_played = {t: 0   for t in teams}
 
        eligible_games = games
        if ovr_filter is not None:
            eligible_games = [
                (t1, t2, s1, s2) for t1, t2, s1, s2 in games
                if abs((off_rating[t1] + def_rating[t1]) -
                       (off_rating[t2] + def_rating[t2])) <= ovr_filter
            ]
 
        for t1, t2, actual_s1, actual_s2 in eligible_games:
            predicted_s1 = off_rating[t1] - def_rating[t2] + league_avg
            predicted_s2 = off_rating[t2] - def_rating[t1] + league_avg
 
            error_s1 = actual_s1 - predicted_s1
            error_s2 = actual_s2 - predicted_s2
 
            off_error[t1] += error_s1
            off_error[t2] += error_s2
            def_error[t1] += -error_s2
            def_error[t2] += -error_s1
 
            games_played[t1] += 1
            games_played[t2] += 1
 
        for team in teams:
            if games_played[team] > 0:
                off_rating[team] += (
                    (off_error[team] / games_played[team]) * LEARNING_RATE
                )
                def_rating[team] += (
                    (def_error[team] / games_played[team]) * LEARNING_RATE
                )
 
        if (iteration + 1) % 100 == 0:
            eligible_count = (
                len(eligible_games) if ovr_filter is not None else len(games)
            )
            print(
                f"  [{phase_label}] Iteration {iteration + 1}/{iterations} complete"
                + (f" | Competitive games: {eligible_count}" if ovr_filter else "")
            )
 
 
def calculate_ratings(all_games, iterations=ITERATIONS):
    games = [(t1, t2, s1, s2) for _, t1, s1, t2, s2 in all_games]
 
    teams = list({t for t1, t2, _, _ in games for t in (t1, t2)})
    if not teams:
        return {}, {}, {}, 0
 
    all_scores = [s for _, _, s1, s2 in games for s in (s1, s2)]
    league_avg = sum(all_scores) / len(all_scores)
    print(f"  League average: {league_avg:.2f} points per game")
 
    off_rating = {t: 0.0 for t in teams}
    def_rating = {t: 0.0 for t in teams}
 
    print(f"\n  Running Phase 1 ({iterations} iterations, all games)...")
    run_iterations(games, teams, off_rating, def_rating, league_avg,
                   iterations=iterations, phase_label="Phase 1", ovr_filter=None)
 
    print(f"\n  Running Phase 2 ({iterations} iterations, "
          f"competitive games within {COMPETITIVE_THRESHOLD} OVR pts)...")
    run_iterations(games, teams, off_rating, def_rating, league_avg,
                   iterations=iterations, phase_label="Phase 2",
                   ovr_filter=COMPETITIVE_THRESHOLD)
 
    ovr_rating = {t: round(off_rating[t] + def_rating[t], 2) for t in teams}
    return off_rating, def_rating, ovr_rating, league_avg
 
 
# ---------------------------------------------------------------------------
# JSON OUTPUT
# ---------------------------------------------------------------------------
 
def build_team_entries(off_rating, def_rating, ovr_rating,
                       team_to_class, team_to_district,
                       class_filter=None):
    all_teams = list(ovr_rating.keys())
 
    pool = (
        [t for t in all_teams if team_to_class.get(t) == class_filter]
        if class_filter is not None
        else all_teams
    )
 
    ovr_sorted = sorted(pool, key=lambda t: ovr_rating[t], reverse=True)
    off_sorted = sorted(pool, key=lambda t: off_rating[t], reverse=True)
    def_sorted = sorted(pool, key=lambda t: def_rating[t], reverse=True)
 
    ovr_rank = {t: i + 1 for i, t in enumerate(ovr_sorted)}
    off_rank = {t: i + 1 for i, t in enumerate(off_sorted)}
    def_rank = {t: i + 1 for i, t in enumerate(def_sorted)}
 
    return [
        {
            "ovr_rank":       ovr_rank[t],
            "school":         t,
            "classification": team_to_class.get(t),
            "district":       team_to_district.get(t),
            "ovr_rating":     ovr_rating[t],
            "off_rating":     round(off_rating[t], 2),
            "off_rank":       off_rank[t],
            "def_rating":     round(def_rating[t], 2),
            "def_rank":       def_rank[t],
        }
        for t in ovr_sorted
    ]
 
 
def save_overall_json(off_rating, def_rating, ovr_rating, league_avg,
                      team_to_class, team_to_district):
    entries = build_team_entries(off_rating, def_rating, ovr_rating,
                                 team_to_class, team_to_district)
    output = {
        "last_updated":   datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        "league_average": round(league_avg, 2),
        "teams": entries,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
 
    print(f"Saved {len(entries)} teams to {OUTPUT_PATH}")
    print("Top 5 overall:")
    for e in entries[:5]:
        print(f"  {e['ovr_rank']}. {e['school']} (Class {e['classification']}) "
              f"| OVR: {e['ovr_rating']:+.2f} "
              f"| OFF: {e['off_rating']:+.2f} "
              f"| DEF: {e['def_rating']:+.2f}")
 
 
def save_class_jsons(off_rating, def_rating, ovr_rating, league_avg,
                     team_to_class, team_to_district):
    for cls in range(1, 7):
        entries = build_team_entries(off_rating, def_rating, ovr_rating,
                                     team_to_class, team_to_district,
                                     class_filter=cls)
        if not entries:
            print(f"  Class {cls}: no teams found — skipping.")
            continue
 
        path = f"football_ratings_2013_class{cls}.json"
        output = {
            "last_updated":   datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            "league_average": round(league_avg, 2),
            "classification": cls,
            "teams": entries,
        }
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
 
        print(f"  Class {cls}: {len(entries)} teams → {path}")
        print("    Top 3: " + " | ".join(
            f"{e['ovr_rank']}. {e['school']} ({e['ovr_rating']:+.2f})"
            for e in entries[:3]
        ))
 
 
 
# ---------------------------------------------------------------------------
# CSV RANKINGS OUTPUT
# ---------------------------------------------------------------------------
 
def save_rankings_csv(off_rating, def_rating, ovr_rating,
                      team_to_class, team_to_district,
                      class_filter=None):
    """
    Save a rankings CSV for either all teams (class_filter=None) or a
    specific class.  Rankings (OFF Rank, DEF Rank, OVR Rank) are computed
    within the pool so class CSVs show class-specific ranks.
 
    Columns: School, OFF Rating, DEF Rating, OVR Rating,
             OFF Rank, DEF Rank, OVR Rank
    """
    all_teams = list(ovr_rating.keys())
 
    pool = (
        [t for t in all_teams if team_to_class.get(t) == class_filter]
        if class_filter is not None
        else all_teams
    )
 
    if not pool:
        label = f"Class {class_filter}" if class_filter else "Overall"
        print(f"  {label}: no teams — skipping CSV.")
        return
 
    ovr_sorted = sorted(pool, key=lambda t: ovr_rating[t], reverse=True)
    off_sorted = sorted(pool, key=lambda t: off_rating[t], reverse=True)
    def_sorted = sorted(pool, key=lambda t: def_rating[t], reverse=True)
 
    ovr_rank = {t: i + 1 for i, t in enumerate(ovr_sorted)}
    off_rank = {t: i + 1 for i, t in enumerate(off_sorted)}
    def_rank = {t: i + 1 for i, t in enumerate(def_sorted)}
 
    rows = [
        {
            "School":      t,
            "OFF Rating":  round(off_rating[t], 2),
            "DEF Rating":  round(def_rating[t], 2),
            "OVR Rating":  round(ovr_rating[t], 2),
            "OFF Rank":    off_rank[t],
            "DEF Rank":    def_rank[t],
            "OVR Rank":    ovr_rank[t],
        }
        for t in ovr_sorted
    ]
 
    df = pd.DataFrame(rows, columns=[
        "School", "OFF Rating", "DEF Rating", "OVR Rating",
        "OFF Rank", "DEF Rank", "OVR Rank"
    ])
 
    if class_filter is None:
        path  = "football_rankings_2013_all.csv"
        label = "All teams"
    else:
        path  = f"football_rankings_2013_class{class_filter}.csv"
        label = f"Class {class_filter}"
 
    df.to_csv(path, index=False)
    print(f"  {label}: {len(df)} teams — {path}")
 
 
def save_all_rankings_csvs(off_rating, def_rating, ovr_rating,
                           team_to_class, team_to_district):
    """Save overall + one CSV per class (1-6)."""
    save_rankings_csv(off_rating, def_rating, ovr_rating,
                      team_to_class, team_to_district,
                      class_filter=None)
    for cls in range(1, 7):
        save_rankings_csv(off_rating, def_rating, ovr_rating,
                          team_to_class, team_to_district,
                          class_filter=cls)
 
# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":
    print("=== MSHSAA Football Ratings 2013 ===")
 
    print("\nLoading classifications...")
    team_to_class, team_to_district = load_classifications()
    known_teams = set(team_to_class.keys())
    print(f"  Loaded {len(team_to_class)} teams from {CLASSIFICATIONS_PATH}")
 
    print("\nBuilding school ID → classification name lookup...")
    id_to_classname = build_id_to_classname(team_to_class, SCHOOLS_CSV)
 
    print("\nScraping season scoreboard...")
    all_games = scrape_full_season(id_to_classname, known_teams)
    print(f"\nTotal valid games (before deduplication): {len(all_games)}")
    if not all_games:
        print("No games found — exiting.")
        exit(1)
 
    if MANUAL_GAMES:
        print(f"\nAdding {len(MANUAL_GAMES)} manual game(s)...")
        all_games.extend(MANUAL_GAMES)
 
    print("\nDeduplicating games...")
    all_games = deduplicate_games(all_games)
 
    print("\nChecking for missing teams...")
    report_missing_teams(all_games, team_to_class)
 
    print("Saving scoreboard CSV...")
    save_csv(all_games)
 
    print(f"\nRunning ratings engine "
          f"({ITERATIONS} Phase 1 + {ITERATIONS} Phase 2 iterations)...")
    off_rating, def_rating, ovr_rating, league_avg = calculate_ratings(all_games)
 
    print("\nSaving overall ratings JSON...")
    save_overall_json(off_rating, def_rating, ovr_rating, league_avg,
                      team_to_class, team_to_district)
 
    print("\nSaving per-class ratings JSONs...")
    save_class_jsons(off_rating, def_rating, ovr_rating, league_avg,
                     team_to_class, team_to_district)
 
    print("\nSaving rankings CSVs...")
    save_all_rankings_csvs(off_rating, def_rating, ovr_rating,
                           team_to_class, team_to_district)
 
    print("\n=== Done ===")
