from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
import os
from django.contrib.auth.models import User

from .models import (
    BallHistory,
    Commentary,
    CurrentPlayers,
    Match,
    PlayerStat,
    PointsTableEntry,
    ScorecardEntry,
    TeamPlayer,
)

TEAM_LOGO_MAP = {
    "PBKS": "dashboard/images/teams/pbks.png",
    "SRH": "dashboard/images/teams/srh.png",
    "MI": "dashboard/images/teams/mi.png",
    "CSK": "dashboard/images/teams/csk.png",
    "RCB": "dashboard/images/teams/rcb.png",
    "KKR": "dashboard/images/teams/kkr.png",
    "DC": "dashboard/images/teams/dc.png",
    "RR": "dashboard/images/teams/rr.png",
    "LSG": "dashboard/images/teams/lsg.png",
    "GT": "dashboard/images/teams/gt.png",
    "Punjab Kings": "dashboard/images/teams/pbks.png",
    "Sunrisers Hyderabad": "dashboard/images/teams/srh.png",
    "Mumbai Indians": "dashboard/images/teams/mi.png",
    "Chennai Super Kings": "dashboard/images/teams/csk.png",
    "Royal Challengers Bangalore": "dashboard/images/teams/rcb.png",
    "Royal Challengers Bengaluru": "dashboard/images/teams/rcb.png",
    "Kolkata Knight Riders": "dashboard/images/teams/kkr.png",
    "Delhi Capitals": "dashboard/images/teams/dc.png",
    "Rajasthan Royals": "dashboard/images/teams/rr.png",
    "Lucknow Super Giants": "dashboard/images/teams/lsg.png",
    "Gujarat Titans": "dashboard/images/teams/gt.png",
}

BALLS_PER_OVER = 6
MAX_OVERS = 20
MAX_WICKETS = 10

def _ensure_render_admin():
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    email = os.environ.get("ADMIN_EMAIL", "")

    if not username or not password:
        return

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )


def _get_team_logo(team_name):
    if not team_name:
        return "dashboard/images/teams/default.png"
    return TEAM_LOGO_MAP.get(team_name.strip(), "dashboard/images/teams/default.png")


def _get_selected_match(match_id=None):
    if match_id:
        return get_object_or_404(Match, pk=match_id)

    live_match = (
        Match.objects.filter(status__in=["In Progress", "Second Innings"])
        .order_by("-created_at")
        .first()
    )
    if live_match:
        return live_match

    return Match.objects.order_by("-created_at").first()


def _parse_over_balls(overs_text):
    try:
        overs_part, balls_part = str(overs_text).split(".", 1)
        return int(overs_part), int(balls_part)
    except (ValueError, AttributeError):
        return 0, 0


def _format_over_balls(overs, balls):
    return f"{overs}.{balls}"


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _advance_overs(current_overs, legal_delivery=True):
    overs, balls = _parse_over_balls(current_overs)

    if legal_delivery:
        balls += 1
        if balls >= BALLS_PER_OVER:
            overs += 1
            balls = 0

    return _format_over_balls(overs, balls)


def _is_innings_complete(match):
    overs, _balls = _parse_over_balls(match.overs)
    return overs >= MAX_OVERS or match.wickets >= MAX_WICKETS


def _event_runs(event):
    event = str(event).upper()

    if event == "W":
        return 0
    if event.isdigit():
        return int(event)
    if event.startswith("WD"):
        return int(event[2:]) if len(event) > 2 else 1
    if event.startswith("NB"):
        return int(event[2:]) if len(event) > 2 else 1
    if event.startswith("LB"):
        return int(event[2:]) if len(event) > 2 else 1
    if event.startswith("B"):
        return int(event[1:]) if len(event) > 1 else 1

    return 0


def _get_current_over_number(match):
    overs, _balls = _parse_over_balls(match.overs)
    return overs + 1


def _generate_commentary(event, batsman="", bowler=""):
    if event == "W":
        return f"WICKET! {bowler} dismisses {batsman}."
    if event == "6":
        return f"SIX! {batsman} launches it into the stands."
    if event == "4":
        return f"FOUR! {batsman} finds the boundary."
    if event == "0":
        return f"Dot ball. Good delivery by {bowler}."
    if event == "1":
        return f"{batsman} takes a single."
    if event == "2":
        return f"{batsman} comes back for two."
    if event == "3":
        return "Three runs taken."
    if str(event).startswith("WD"):
        return "Wide ball."
    if str(event).startswith("NB"):
        return "No ball called."
    if str(event).startswith("LB"):
        return "Leg bye taken."
    if str(event).startswith("B"):
        return "Bye taken."
    return "Ball completed."


def calculate_win_probability(runs_needed, balls_left, wickets_left):
    if runs_needed <= 0:
        return 100.0
    if balls_left <= 0:
        return 0.0

    required_rate = (runs_needed / balls_left) * 6
    base = 75 - (required_rate * 6)
    base += wickets_left * 1.5
    probability = max(5, min(95, base))
    return round(probability, 1)


def _swap_batsmen(players):
    players.batsman, players.non_striker = players.non_striker, players.batsman
    players.batsman_runs, players.non_striker_runs = players.non_striker_runs, players.batsman_runs
    players.batsman_balls, players.non_striker_balls = players.non_striker_balls, players.batsman_balls


def _get_or_create_scorecard_entry(match, innings, player_name, team):
    entry, _ = ScorecardEntry.objects.get_or_create(
        match=match,
        innings=innings,
        player_name=player_name,
        defaults={
            "team": team,
            "runs": 0,
            "balls": 0,
            "fours": 0,
            "sixes": 0,
            "strike_rate": 0,
            "wicket_info": "",
            "dismissal_type": "",
            "fielder_name": "",
            "is_out": False,
        },
    )
    return entry


def _update_scorecard_strike_rate(entry):
    entry.strike_rate = round((entry.runs / entry.balls) * 100, 2) if entry.balls else 0
    entry.save()


def _ensure_current_batters_in_scorecard(match, players):
    batting_team = match.batting_team or ""

    if players.batsman:
        _get_or_create_scorecard_entry(match, match.innings, players.batsman, batting_team)
    if players.non_striker:
        _get_or_create_scorecard_entry(match, match.innings, players.non_striker, batting_team)


def _save_playing_xi(match, team_name, player_names):
    TeamPlayer.objects.filter(match=match, team=team_name).delete()

    for name in player_names:
        clean_name = name.strip()
        if clean_name:
            TeamPlayer.objects.create(
                match=match,
                team=team_name,
                player_name=clean_name,
                is_playing_xi=True,
            )


def _get_team_players(match, team_name):
    return TeamPlayer.objects.filter(
        match=match,
        team=team_name,
        is_playing_xi=True,
    ).order_by("id")


def _build_wicket_info(dismissal_type, bowler="", fielder=""):
    dismissal_type = (dismissal_type or "").strip().lower()
    bowler = (bowler or "").strip()
    fielder = (fielder or "").strip()

    if dismissal_type == "bowled":
        return f"b {bowler}" if bowler else "b Bowler"
    if dismissal_type == "caught":
        if fielder and bowler:
            return f"c {fielder} b {bowler}"
        if bowler:
            return f"c Fielder b {bowler}"
        return "c Fielder"
    if dismissal_type == "lbw":
        return f"lbw b {bowler}" if bowler else "lbw"
    if dismissal_type == "run_out":
        return f"run out ({fielder})" if fielder else "run out"
    if dismissal_type == "stumped":
        if fielder and bowler:
            return f"st {fielder} b {bowler}"
        if bowler:
            return f"st Keeper b {bowler}"
        return "st Keeper"
    if dismissal_type == "hit_wicket":
        return f"hit wicket b {bowler}" if bowler else "hit wicket"

    return f"b {bowler}" if bowler else "out"


def _create_match(request):
    team1 = request.POST.get("team1", "").strip()
    team2 = request.POST.get("team2", "").strip()

    if not team1 or not team2:
        return None

    match = Match.objects.create(
        team1=team1,
        team2=team2,
        batting_team=team1,
        bowling_team=team2,
        runs=0,
        wickets=0,
        overs="0.0",
        status="In Progress",
        result_text="First innings live",
        innings=1,
        first_innings_runs=0,
        first_innings_wickets=0,
        first_innings_overs="0.0",
        target=0,
        partnership_runs=0,
        partnership_balls=0,
        last_wicket_text="",
    )

    players = CurrentPlayers.objects.create(
        match=match,
        batsman=request.POST.get("batsman", "").strip() or "Striker",
        non_striker=request.POST.get("non_striker", "").strip() or "Non-Striker",
        bowler=request.POST.get("bowler", "").strip() or "Bowler",
        batsman_runs=0,
        batsman_balls=0,
        non_striker_runs=0,
        non_striker_balls=0,
        bowler_wickets=0,
    )

    _ensure_current_batters_in_scorecard(match, players)

    team1_players = request.POST.getlist("team1_players")
    team2_players = request.POST.getlist("team2_players")
    _save_playing_xi(match, team1, team1_players)
    _save_playing_xi(match, team2, team2_players)

    return match


def _update_players(match, request):
    players, _ = CurrentPlayers.objects.get_or_create(match=match)

    batsman = request.POST.get("batsman", "").strip()
    non_striker = request.POST.get("non_striker", "").strip()
    bowler = request.POST.get("bowler", "").strip()

    players.batsman = batsman or players.batsman
    players.non_striker = non_striker or players.non_striker
    players.bowler = bowler or players.bowler

    players.batsman_runs = _to_int(request.POST.get("batsman_runs"), players.batsman_runs)
    players.batsman_balls = _to_int(request.POST.get("batsman_balls"), players.batsman_balls)
    players.non_striker_runs = _to_int(request.POST.get("non_striker_runs"), players.non_striker_runs)
    players.non_striker_balls = _to_int(request.POST.get("non_striker_balls"), players.non_striker_balls)
    players.bowler_wickets = _to_int(request.POST.get("bowler_wickets"), players.bowler_wickets)
    players.save()

    _ensure_current_batters_in_scorecard(match, players)


def _update_player_stat(request):
    name = request.POST.get("stat_name", "").strip()
    if not name:
        return

    runs = _to_int(request.POST.get("stat_runs"))
    balls = _to_int(request.POST.get("stat_balls"))
    wickets = _to_int(request.POST.get("stat_wickets"))
    strike_rate = round((runs / balls) * 100, 2) if balls else 0

    PlayerStat.objects.update_or_create(
        name=name,
        defaults={
            "team": request.POST.get("stat_team", "").strip(),
            "runs": runs,
            "balls": balls,
            "wickets": wickets,
            "strike_rate": strike_rate,
        },
    )


def _update_points_table(request):
    team = request.POST.get("points_team", "").strip()
    if not team:
        return
    
    points = [
    {
        "team": p.team,
        "played": p.played,
        "won": p.won,
        "lost": p.lost,
        "tied": p.tied,
        "no_result": p.no_result,
        "points": p.points,
        "net_run_rate": p.net_run_rate,
        "logo": _get_team_logo(p.team),
    }
    for p in PointsTableEntry.objects.all().order_by('-points')
]
    
    PointsTableEntry.objects.update_or_create(
        team=team,
        defaults={
            "played": _to_int(request.POST.get("played")),
            "won": _to_int(request.POST.get("won")),
            "lost": _to_int(request.POST.get("lost")),
            "tied": _to_int(request.POST.get("tied")),
            "no_result": _to_int(request.POST.get("no_result")),
            "points": _to_int(request.POST.get("points")),
            "net_run_rate": _to_float(request.POST.get("net_run_rate")),
        },
    )


def _start_second_innings(match):
    match.first_innings_runs = match.runs
    match.first_innings_wickets = match.wickets
    match.first_innings_overs = match.overs
    match.target = match.runs + 1

    old_batting = match.batting_team
    old_bowling = match.bowling_team

    match.batting_team = old_bowling
    match.bowling_team = old_batting

    match.runs = 0
    match.wickets = 0
    match.overs = "0.0"
    match.innings = 2
    match.status = "Second Innings"
    match.result_text = f"Target: {match.target}"
    match.partnership_runs = 0
    match.partnership_balls = 0
    match.last_wicket_text = ""
    match.save()

    players = CurrentPlayers.objects.filter(match=match).first()
    if players:
        players.batsman = "Striker"
        players.batsman_runs = 0
        players.batsman_balls = 0
        players.non_striker = "Non-Striker"
        players.non_striker_runs = 0
        players.non_striker_balls = 0
        players.bowler = "Bowler"
        players.bowler_wickets = 0
        players.save()

        _ensure_current_batters_in_scorecard(match, players)


def _assign_player_of_match(match):
    candidates = []
    scorecard_rows = ScorecardEntry.objects.filter(match=match)

    for row in scorecard_rows:
        score = row.runs + (row.fours * 1) + (row.sixes * 2)
        player_stat = PlayerStat.objects.filter(name=row.player_name, team=row.team).first()
        wickets = player_stat.wickets if player_stat else 0
        score += wickets * 25

        candidates.append(
            {
                "name": row.player_name,
                "team": row.team,
                "runs": row.runs,
                "wickets": wickets,
                "score": score,
            }
        )

    if not candidates:
        return

    best = max(candidates, key=lambda x: x["score"])
    match.player_of_match = best["name"]
    match.player_of_match_team = best["team"]

    if best["wickets"] > 0:
        match.player_of_match_figures = f"{best['runs']} runs, {best['wickets']} wkts"
    else:
        match.player_of_match_figures = f"{best['runs']} runs"

    match.save()


def _finish_match_with_result(match):
    if match.runs >= match.target and match.innings == 2:
        wickets_left = MAX_WICKETS - match.wickets
        match.result_text = f"{match.batting_team} won by {wickets_left} wickets"
        match.status = "Completed"
    elif match.innings == 2 and (match.wickets >= MAX_WICKETS or match.overs == "20.0"):
        runs_diff = max(match.target - match.runs - 1, 0)
        if runs_diff == 0:
            match.result_text = "Match tied"
        else:
            match.result_text = f"{match.bowling_team} won by {runs_diff} runs"
        match.status = "Completed"

    _assign_player_of_match(match)
    match.save()


def _save_commentary(match, event, players):
    over_no, ball_no = _parse_over_balls(match.overs)
    over_text = f"{over_no}.{ball_no}"

    Commentary.objects.create(
        match=match,
        over_text=over_text,
        event=event,
        text=_generate_commentary(
            event=event,
            batsman=players.batsman if players else "",
            bowler=players.bowler if players else "",
        ),
    )


def _record_ball(match, request):
    if match.status == "Completed":
        return

    event_type = request.POST.get("event_type", "run")
    run_value = _to_int(request.POST.get("runs", "0"))

    players, _ = CurrentPlayers.objects.get_or_create(
        match=match,
        defaults={
            "batsman": "Striker",
            "non_striker": "Non-Striker",
            "bowler": "Bowler",
        },
    )

    _ensure_current_batters_in_scorecard(match, players)

    striker_name_before = players.batsman
    striker_runs_before = players.batsman_runs
    striker_balls_before = players.batsman_balls

    striker_entry = _get_or_create_scorecard_entry(
        match, match.innings, players.batsman, match.batting_team
    )
    _get_or_create_scorecard_entry(
        match, match.innings, players.non_striker, match.batting_team
    )

    legal_delivery = True
    ball_event = "0"

    if event_type == "run":
        match.runs += run_value
        players.batsman_runs += run_value
        players.batsman_balls += 1

        striker_entry.runs += run_value
        striker_entry.balls += 1
        if run_value == 4:
            striker_entry.fours += 1
        elif run_value == 6:
            striker_entry.sixes += 1
        _update_scorecard_strike_rate(striker_entry)

        ball_event = str(run_value)

        match.partnership_runs += run_value
        match.partnership_balls += 1

        if run_value % 2 == 1:
            _swap_batsmen(players)

    elif event_type == "wicket":
        dismissal_type = request.POST.get("dismissal_type", "bowled").strip()
        fielder_name = request.POST.get("fielder_name", "").strip()

        match.wickets += 1
        players.batsman_balls += 1
        players.bowler_wickets += 1

        striker_entry.balls += 1
        striker_entry.is_out = True
        striker_entry.dismissal_type = dismissal_type
        striker_entry.fielder_name = fielder_name
        striker_entry.wicket_info = _build_wicket_info(
            dismissal_type=dismissal_type,
            bowler=players.bowler,
            fielder=fielder_name,
        )
        _update_scorecard_strike_rate(striker_entry)

        ball_event = "W"

        match.last_wicket_text = f"{striker_name_before} {striker_runs_before}({striker_balls_before + 1})"
        match.partnership_runs = 0
        match.partnership_balls = 0

        next_batsman = request.POST.get("next_batsman", "").strip() or "New Batsman"
        players.batsman = next_batsman
        players.batsman_runs = 0
        players.batsman_balls = 0

        _get_or_create_scorecard_entry(match, match.innings, players.batsman, match.batting_team)

    elif event_type == "wide":
        run_value = max(run_value, 1)
        match.runs += run_value
        legal_delivery = False
        ball_event = f"WD{run_value}"
        match.partnership_runs += run_value

    elif event_type == "no_ball":
        run_value = max(run_value, 1)
        match.runs += run_value
        legal_delivery = False
        ball_event = f"NB{run_value}"
        match.partnership_runs += run_value

    elif event_type == "leg_bye":
        run_value = max(run_value, 1)
        match.runs += run_value
        players.batsman_balls += 1

        striker_entry.balls += 1
        _update_scorecard_strike_rate(striker_entry)

        ball_event = f"LB{run_value}"
        match.partnership_runs += run_value
        match.partnership_balls += 1

        if run_value % 2 == 1:
            _swap_batsmen(players)

    elif event_type == "bye":
        run_value = max(run_value, 1)
        match.runs += run_value
        players.batsman_balls += 1

        striker_entry.balls += 1
        _update_scorecard_strike_rate(striker_entry)

        ball_event = f"B{run_value}"
        match.partnership_runs += run_value
        match.partnership_balls += 1

        if run_value % 2 == 1:
            _swap_batsmen(players)

    ball_over = _get_current_over_number(match)

    BallHistory.objects.create(
        match=match,
        event=ball_event,
        over_no=ball_over,
    )

    new_overs_text = _advance_overs(match.overs, legal_delivery=legal_delivery)
    _overs_after, balls_after = _parse_over_balls(new_overs_text)

    if legal_delivery and balls_after == 0:
        _swap_batsmen(players)

    match.overs = new_overs_text

    players.save()
    match.save()

    _save_commentary(match, ball_event, players)

    if match.innings == 1 and _is_innings_complete(match):
        _start_second_innings(match)
    elif match.innings == 2 and (match.runs >= match.target or _is_innings_complete(match)):
        _finish_match_with_result(match)


def _undo_last_ball(match):
    players = CurrentPlayers.objects.filter(match=match).first()
    last_ball = BallHistory.objects.filter(match=match).order_by("-created_at", "-id").first()

    if not last_ball:
        return

    event = str(last_ball.event).upper()

    if event == "W":
        match.wickets = max(match.wickets - 1, 0)
        if players:
            players.batsman_balls = max(players.batsman_balls - 1, 0)
            players.bowler_wickets = max(players.bowler_wickets - 1, 0)
    elif event.startswith("WD") or event.startswith("NB"):
        match.runs = max(match.runs - _event_runs(event), 0)
    elif event.startswith("LB") or event.startswith("B"):
        match.runs = max(match.runs - _event_runs(event), 0)
        if players:
            players.batsman_balls = max(players.batsman_balls - 1, 0)
    else:
        runs = _event_runs(event)
        match.runs = max(match.runs - runs, 0)
        if players:
            players.batsman_runs = max(players.batsman_runs - runs, 0)
            players.batsman_balls = max(players.batsman_balls - 1, 0)

    if not (event.startswith("WD") or event.startswith("NB")):
        overs, balls = _parse_over_balls(match.overs)
        if balls == 0 and overs > 0:
            overs -= 1
            balls = BALLS_PER_OVER - 1
        else:
            balls = max(balls - 1, 0)
        match.overs = _format_over_balls(overs, balls)

    last_commentary = Commentary.objects.filter(match=match).order_by("-created_at", "-id").first()
    if last_commentary:
        last_commentary.delete()

    if players:
        players.save()
    match.save()
    last_ball.delete()


def index(request):
    matches = Match.objects.order_by("-created_at")
    selected_match = _get_selected_match(request.GET.get("match_id"))

    if not selected_match:
        return render(
            request,
            "dashboard/index.html",
            {
                "match": None,
                "matches": matches,
                "team1_logo": "dashboard/images/teams/default.png",
                "team2_logo": "dashboard/images/teams/default.png",
                "player_stats": PlayerStat.objects.order_by("-runs", "-wickets", "name")[:8],
                "points_table": PointsTableEntry.objects.all()[:10],
            },
        )

    team1_logo = _get_team_logo(selected_match.team1)
    team2_logo = _get_team_logo(selected_match.team2)

    return render(
        request,
        "dashboard/index.html",
        {
            "match": selected_match,
            "matches": matches,
            "team1_logo": team1_logo,
            "team2_logo": team2_logo,
            "player_stats": PlayerStat.objects.order_by("-runs", "-wickets", "name")[:8],
            "points_table": PointsTableEntry.objects.all()[:10],
        },
    )


def login_view(request):
    _ensure_render_admin()

    if request.user.is_authenticated:
        return redirect("admin_panel")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("admin_panel")

        messages.error(request, "Invalid username or password")

    return render(request, "dashboard/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def admin_panel(request):
    selected_match = _get_selected_match(request.GET.get("match_id"))

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_match":
            selected_match = _create_match(request) or selected_match

        elif action == "delete_match" and selected_match:
            selected_match.delete()
            return redirect("/admin-panel/")

        elif selected_match:
             if action == "update_players":
                  _update_players(selected_match, request)
             elif action == "record_ball":
                _record_ball(selected_match, request)
             elif action == "undo_ball":
                _undo_last_ball(selected_match)
            elif action == "edit_scorecard":
               _edit_scorecard_entry(selected_match, request)
            elif action == "finish_match":
               selected_match.status = request.POST.get("status", "Completed")
               selected_match.result_text = request.POST.get("result_text", "").strip()
               selected_match.save()
               if selected_match.status == "Completed":
                  _assign_player_of_match(selected_match)

        if action == "update_player_stat":
            _update_player_stat(request)
        elif action == "update_points_table":
            _update_points_table(request)

        if selected_match:
            return redirect(f"/admin-panel/?match_id={selected_match.id}")
        return redirect("/admin-panel/")

    matches = Match.objects.order_by("-created_at")
    players = CurrentPlayers.objects.filter(match=selected_match).first() if selected_match else None
    recent_balls = (
        BallHistory.objects.filter(match=selected_match).order_by("-created_at", "-id")[:12]
        if selected_match else []
    )
    recent_commentary = (
        Commentary.objects.filter(match=selected_match).order_by("-created_at", "-id")[:10]
        if selected_match else []
    )

    batting_xi = _get_team_players(selected_match, selected_match.batting_team) if selected_match else []
    bowling_xi = _get_team_players(selected_match, selected_match.bowling_team) if selected_match else []
    team1_xi = _get_team_players(selected_match, selected_match.team1) if selected_match else []
    team2_xi = _get_team_players(selected_match, selected_match.team2) if selected_match else []

    return render(
        request,
        "dashboard/admin_panel.html",
        {
            "matches": matches,
            "selected_match": selected_match,
            "players": players,
            "recent_balls": recent_balls,
            "recent_commentary": recent_commentary,
            "player_stats": PlayerStat.objects.order_by("-runs", "-wickets", "name")[:10],
            "points_table": [
         {
        "team": row.team,
        "played": row.played,
        "won": row.won,
        "lost": row.lost,
        "tied": row.tied,
        "no_result": row.no_result,
        "points": row.points,
        "net_run_rate": row.net_run_rate,
        "logo": _get_team_logo(row.team),
        }
          for row in PointsTableEntry.objects.all().order_by("-points", "-net_run_rate", "team")[:10]
        ],
            "batting_xi": batting_xi,
            "bowling_xi": bowling_xi,
            "team1_xi": team1_xi,
            "team2_xi": team2_xi,
        },
    )


def matches_page(request):
    matches = Match.objects.order_by("-created_at")
    for match in matches:
        match.team1_logo = _get_team_logo(match.team1)
        match.team2_logo = _get_team_logo(match.team2)

    return render(request, "dashboard/matches.html", {"matches": matches})


def get_score(request):
    match = _get_selected_match(request.GET.get("match_id"))

    if not match:
        return JsonResponse(
            {
                "team1": "Team A",
                "team2": "Team B",
                "batting_team": "Team A",
                "bowling_team": "Team B",
                "runs": 0,
                "wickets": 0,
                "overs": "0.0",
                "status": "No Match",
                "result_text": "",
                "innings": 1,
                "target": 0,
                "first_innings_runs": 0,
                "win_probability": 50.0,
                "partnership_runs": 0,
                "partnership_balls": 0,
                "last_wicket_text": "",
                "player_of_match": "",
                "player_of_match_team": "",
                "player_of_match_figures": "",
            }
        )

    win_probability = 50.0

    if match.innings == 2:
        overs_part, balls_part = str(match.overs).split(".")
        balls_played = (int(overs_part) * 6) + int(balls_part)
        balls_left = max(0, 120 - balls_played)
        runs_needed = max(0, match.target - match.runs)
        wickets_left = max(0, 10 - match.wickets)

        win_probability = calculate_win_probability(runs_needed, balls_left, wickets_left)

    return JsonResponse(
        {
            "team1": match.team1,
            "team2": match.team2,
            "batting_team": match.batting_team,
            "bowling_team": match.bowling_team,
            "runs": match.runs,
            "wickets": match.wickets,
            "overs": match.overs,
            "status": match.status,
            "result_text": match.result_text,
            "innings": match.innings,
            "target": match.target,
            "first_innings_runs": match.first_innings_runs,
            "win_probability": win_probability,
            "partnership_runs": match.partnership_runs,
            "partnership_balls": match.partnership_balls,
            "last_wicket_text": match.last_wicket_text,
            "player_of_match": match.player_of_match,
            "player_of_match_team": match.player_of_match_team,
            "player_of_match_figures": match.player_of_match_figures,
        }
    )


def players_api(request):
    match = _get_selected_match(request.GET.get("match_id"))
    players = CurrentPlayers.objects.filter(match=match).first() if match else None

    return JsonResponse(
        {
            "name": players.batsman if players else "No batsman",
            "runs": players.batsman_runs if players else 0,
            "balls": players.batsman_balls if players else 0,
            "non_striker": players.non_striker if players else "No non-striker",
            "non_striker_runs": players.non_striker_runs if players else 0,
            "non_striker_balls": players.non_striker_balls if players else 0,
            "bowler": players.bowler if players else "No bowler",
            "bowler_wickets": players.bowler_wickets if players else 0,
            "bowl_wickets": players.bowler_wickets if players else 0,
        }
    )


def player_stats_api(request):
    player_stats = list(
        PlayerStat.objects.order_by("-runs", "-wickets", "name").values(
            "name", "team", "runs", "balls", "wickets", "strike_rate"
        )[:8]
    )
    return JsonResponse({"players": player_stats})


def points_table_api(request):
    rows = []
    for row in PointsTableEntry.objects.all()[:10]:
        rows.append(
            {
                "team": row.team,
                "played": row.played,
                "won": row.won,
                "lost": row.lost,
                "tied": row.tied,
                "no_result": row.no_result,
                "points": row.points,
                "net_run_rate": row.net_run_rate,
                "logo": _get_team_logo(row.team),
            }
        )
    return JsonResponse({"teams": rows})


def commentary_api(request):
    match = _get_selected_match(request.GET.get("match_id"))
    if not match:
        return JsonResponse({"commentary": []})

    commentary_rows = list(
        Commentary.objects.filter(match=match)
        .order_by("-created_at", "-id")
        .values("over_text", "event", "text")[:10]
    )
    return JsonResponse({"commentary": commentary_rows})


def over_data(request):
    match = _get_selected_match(request.GET.get("match_id"))

    if not match:
        return JsonResponse(
            {
                "over_no": 1,
                "balls": [],
                "total": 0,
                "legal_balls": 0,
            }
        )

    overs, balls = _parse_over_balls(match.overs)

    if balls == 0:
        return JsonResponse(
            {
                "over_no": overs + 1,
                "balls": [],
                "total": 0,
                "legal_balls": 0,
            }
        )

    current_over_no = overs + 1

    all_balls = list(
        BallHistory.objects.filter(match=match)
        .order_by("-created_at", "-id")
        .values_list("event", flat=True)
    )

    filtered_balls_reversed = []
    legal_count = 0

    for event in all_balls:
        event_text = str(event).upper()
        filtered_balls_reversed.append(event)

        if not (event_text.startswith("WD") or event_text.startswith("NB")):
            legal_count += 1

        if legal_count == balls:
            break

    filtered_balls = list(reversed(filtered_balls_reversed))
    total = sum(_event_runs(event) for event in filtered_balls)

    return JsonResponse(
        {
            "over_no": current_over_no,
            "balls": filtered_balls,
            "total": total,
            "legal_balls": legal_count,
        }
    )


def chart_data(request):
    match = _get_selected_match(request.GET.get("match_id"))

    if not match:
        return JsonResponse(
            {
                "labels": [],
                "first_innings_runs": [],
                "second_innings_runs": [],
            }
        )

    all_balls = list(
        BallHistory.objects.filter(match=match)
        .order_by("created_at", "id")
        .values_list("event", flat=True)
    )

    first_innings_legal_balls = 0
    if match.first_innings_overs:
        first_overs, first_balls = _parse_over_balls(match.first_innings_overs)
        first_innings_legal_balls = (first_overs * 6) + first_balls

    first_balls_list = []
    second_balls_list = []

    if match.innings == 1:
        first_balls_list = all_balls
    else:
        legal_seen = 0
        split_index = 0

        for i, event in enumerate(all_balls):
            event_text = str(event).upper()
            if not (event_text.startswith("WD") or event_text.startswith("NB")):
                legal_seen += 1
            if legal_seen == first_innings_legal_balls:
                split_index = i + 1
                break

        first_balls_list = all_balls[:split_index]
        second_balls_list = all_balls[split_index:]

    def build_innings_progress(ball_list, prefix="Over"):
        labels = []
        runs = []
        cumulative = 0
        over_total = 0
        legal_count = 0
        over_no = 1

        for event in ball_list:
            over_total += _event_runs(event)
            event_text = str(event).upper()

            if not (event_text.startswith("WD") or event_text.startswith("NB")):
                legal_count += 1

            if legal_count == 6:
                cumulative += over_total
                labels.append(f"{prefix} {over_no}")
                runs.append(cumulative)
                over_no += 1
                over_total = 0
                legal_count = 0

        if over_total > 0 or legal_count > 0:
            cumulative += over_total
            labels.append(f"{prefix} {over_no}")
            runs.append(cumulative)

        return labels, runs

    first_labels, first_runs = build_innings_progress(first_balls_list, "Over")
    second_labels, second_runs = build_innings_progress(second_balls_list, "Over")

    max_len = max(len(first_labels), len(second_labels))
    labels = [f"Over {i}" for i in range(1, max_len + 1)]

    first_dataset = []
    second_dataset = []

    for i in range(max_len):
        first_dataset.append(first_runs[i] if i < len(first_runs) else None)
        second_dataset.append(second_runs[i] if i < len(second_runs) else None)

    return JsonResponse(
        {
            "labels": labels,
            "first_innings_runs": first_dataset,
            "second_innings_runs": second_dataset,
        }
    )


def player_stats_page(request):
    stats = PlayerStat.objects.order_by("-runs", "-wickets", "name")
    return render(request, "dashboard/player_stats.html", {"player_stats": stats})


def points_table_page(request):
    rows = list(PointsTableEntry.objects.all().order_by("-points", "-net_run_rate", "team"))

    for row in rows:
        row.logo = _get_team_logo(row.team)

    return render(
        request,
        "dashboard/points_table.html",
        {"points_table": rows},
    )

def scorecard_page(request):
    match = _get_selected_match(request.GET.get("match_id"))

    if not match:
        return render(
            request,
            "dashboard/scorecard.html",
            {
                "match": None,
                "first_innings_scorecard": [],
                "second_innings_scorecard": [],
            },
        )

    first_innings_scorecard = ScorecardEntry.objects.filter(
        match=match,
        innings=1,
    ).order_by("-runs", "player_name")

    second_innings_scorecard = ScorecardEntry.objects.filter(
        match=match,
        innings=2,
    ).order_by("-runs", "player_name")

    return render(
        request,
        "dashboard/scorecard.html",
        {
            "match": match,
            "first_innings_scorecard": first_innings_scorecard,
            "second_innings_scorecard": second_innings_scorecard,
        },
    )

@login_required
def edit_scorecard_page(request):
    match = _get_selected_match(request.GET.get("match_id"))

    if not match:
        return render(
            request,
            "dashboard/edit_scorecard.html",
            {
                "match": None,
                "first_innings_scorecard": [],
                "second_innings_scorecard": [],
            },
        )

    if request.method == "POST":
        _edit_scorecard_entry(match, request)
        return redirect(f"/edit-scorecard/?match_id={match.id}")

    first_innings_scorecard = ScorecardEntry.objects.filter(
        match=match,
        innings=1,
    ).order_by("-runs", "player_name")

    second_innings_scorecard = ScorecardEntry.objects.filter(
        match=match,
        innings=2,
    ).order_by("-runs", "player_name")

    return render(
        request,
        "dashboard/edit_scorecard.html",
        {
            "match": match,
            "first_innings_scorecard": first_innings_scorecard,
            "second_innings_scorecard": second_innings_scorecard,
        },
    )
