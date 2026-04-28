import os
import re
import requests

API_KEY = os.getenv("CRICKET_API_KEY", "YOUR_API_KEY")


def parse_score_line(score_line):
    """
    Handles formats like:
    'India 120/3 (12.4)'
    'RCB 89/2 (9.1 ov)'
    """
    if not score_line:
        return 0, 0, "0.0"

    text = str(score_line)

    score_match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    overs_match = re.search(r"\((\d+\.\d+)", text)

    runs = int(score_match.group(1)) if score_match else 0
    wickets = int(score_match.group(2)) if score_match else 0
    overs = overs_match.group(1) if overs_match else "0.0"

    return runs, wickets, overs


def get_live_match():
    url = "https://api.cricapi.com/v1/currentMatches"

    try:
        response = requests.get(
            url,
            params={"apikey": API_KEY, "offset": 0},
            timeout=10,
        )
        data = response.json()

        if data.get("status") != "success":
            return None

        matches = data.get("data", [])

        for match in matches:
            if not match.get("matchStarted"):
                continue

            teams = match.get("teams", ["Team A", "Team B"])
            score_list = match.get("score", [])

            runs = 0
            wickets = 0
            overs = "0.0"
            batting_team = teams[0] if teams else "Team A"

            if score_list:
                latest_score = score_list[-1]

                batting_team = (
                    latest_score.get("inning")
                    or latest_score.get("team")
                    or batting_team
                )

                if "r" in latest_score:
                    runs = latest_score.get("r", 0)
                    wickets = latest_score.get("w", 0)
                    overs = str(latest_score.get("o", "0.0"))
                else:
                    runs, wickets, overs = parse_score_line(str(latest_score))

            bowling_team = teams[1] if batting_team == teams[0] else teams[0]

            return {
                "team1": teams[0] if len(teams) > 0 else "Team A",
                "team2": teams[1] if len(teams) > 1 else "Team B",
                "batting_team": batting_team,
                "bowling_team": bowling_team,
                "runs": runs,
                "wickets": wickets,
                "overs": overs,
                "status": match.get("status", "Live"),
                "api": True,
            }

        return None

    except Exception:
        return None