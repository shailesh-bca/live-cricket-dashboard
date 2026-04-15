from django.test import TestCase
from django.urls import reverse

from .models import BallHistory, CurrentPlayers, Match, PlayerStat, PointsTableEntry


class DashboardViewTests(TestCase):
    def test_score_endpoints_use_database_values(self):
        match = Match.objects.create(team1="MI", team2="CSK", runs=42, wickets=2, overs="5.3")
        CurrentPlayers.objects.create(
            match=match,
            batsman="Rohit",
            batsman_runs=30,
            batsman_balls=18,
            bowler="Jadeja",
            bowler_wickets=1,
        )

        response = self.client.get(reverse("get_score"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["team1"], "MI")
        self.assertEqual(response.json()["runs"], 42)

        players_response = self.client.get(reverse("players_api"))
        self.assertEqual(players_response.json()["name"], "Rohit")
        self.assertEqual(players_response.json()["bowl_wickets"], 1)

    def test_admin_panel_can_create_and_score_match(self):
        create_response = self.client.post(
            reverse("admin_panel"),
            {
                "action": "create_match",
                "team1": "RCB",
                "team2": "GT",
                "batsman": "Virat",
                "bowler": "Shami",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        match = Match.objects.get(team1="RCB", team2="GT")
        self.client.post(
            reverse("admin_panel") + f"?match_id={match.id}",
            {
                "action": "record_ball",
                "event_type": "run",
                "runs": "4",
                "status": "In Progress",
            },
        )

        match.refresh_from_db()
        players = CurrentPlayers.objects.get(match=match)
        self.assertEqual(match.runs, 4)
        self.assertEqual(match.overs, "0.1")
        self.assertEqual(players.batsman_runs, 4)
        self.assertEqual(BallHistory.objects.filter(match=match).count(), 1)

    def test_chart_data_returns_cumulative_over_totals(self):
        match = Match.objects.create(team1="KKR", team2="SRH")
        BallHistory.objects.create(match=match, event="1", over_no=1)
        BallHistory.objects.create(match=match, event="4", over_no=1)
        BallHistory.objects.create(match=match, event="W", over_no=1)
        BallHistory.objects.create(match=match, event="2", over_no=2)

        response = self.client.get(reverse("chart_data"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["labels"], ["Over 1", "Over 2"])
        self.assertEqual(response.json()["runs"], [5, 7])

    def test_admin_panel_supports_extras_and_undo(self):
        match = Match.objects.create(team1="DC", team2="PBKS")
        CurrentPlayers.objects.create(match=match, batsman="Warner", bowler="Rabada")

        self.client.post(
            reverse("admin_panel") + f"?match_id={match.id}",
            {"action": "record_ball", "event_type": "wide", "runs": "1", "status": "In Progress"},
        )
        self.client.post(
            reverse("admin_panel") + f"?match_id={match.id}",
            {"action": "record_ball", "event_type": "leg_bye", "runs": "2", "status": "In Progress"},
        )

        match.refresh_from_db()
        self.assertEqual(match.runs, 3)
        self.assertEqual(match.overs, "0.1")

        self.client.post(reverse("admin_panel") + f"?match_id={match.id}", {"action": "undo_ball"})
        match.refresh_from_db()
        self.assertEqual(match.runs, 1)
        self.assertEqual(match.overs, "0.0")

    def test_stats_and_points_table_apis_return_saved_rows(self):
        PlayerStat.objects.create(name="Gill", team="GT", runs=72, balls=45, wickets=0, strike_rate=160)
        PointsTableEntry.objects.create(team="GT", played=3, won=2, lost=1, points=4, net_run_rate=0.455)

        stats_response = self.client.get(reverse("player_stats_api"))
        points_response = self.client.get(reverse("points_table_api"))

        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()["players"][0]["name"], "Gill")
        self.assertEqual(points_response.status_code, 200)
        self.assertEqual(points_response.json()["teams"][0]["team"], "GT")
