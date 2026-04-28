from django.db import models


class Match(models.Model):
    team1 = models.CharField(max_length=100)
    team2 = models.CharField(max_length=100)

    batting_team = models.CharField(max_length=100, blank=True, default="")
    bowling_team = models.CharField(max_length=100, blank=True, default="")

    runs = models.IntegerField(default=0)
    wickets = models.IntegerField(default=0)
    overs = models.CharField(max_length=10, default="0.0")

    status = models.CharField(max_length=50, default="In Progress")
    result_text = models.CharField(max_length=255, blank=True, default="")

    innings = models.IntegerField(default=1)
    first_innings_runs = models.IntegerField(default=0)
    first_innings_wickets = models.IntegerField(default=0)
    first_innings_overs = models.CharField(max_length=10, default="0.0")
    target = models.IntegerField(default=0)

    # new fields
    last_wicket_text = models.CharField(max_length=255, blank=True, default="")
    partnership_runs = models.IntegerField(default=0)
    partnership_balls = models.IntegerField(default=0)

    player_of_match = models.CharField(max_length=100, blank=True, default="")
    player_of_match_team = models.CharField(max_length=100, blank=True, default="")
    player_of_match_figures = models.CharField(max_length=100, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.team1} vs {self.team2}"


class BallHistory(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    event = models.CharField(max_length=20)
    over_no = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.match} - {self.event}"


class CurrentPlayers(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)

    batsman = models.CharField(max_length=100)
    batsman_runs = models.IntegerField(default=0)
    batsman_balls = models.IntegerField(default=0)

    non_striker = models.CharField(max_length=100, default="Non-Striker")
    non_striker_runs = models.IntegerField(default=0)
    non_striker_balls = models.IntegerField(default=0)

    bowler = models.CharField(max_length=100)
    bowler_wickets = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.batsman} & {self.non_striker} / {self.bowler}"


class ScorecardEntry(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    innings = models.IntegerField(default=1)

    player_name = models.CharField(max_length=100)
    team = models.CharField(max_length=100, blank=True, default="")

    runs = models.IntegerField(default=0)
    balls = models.IntegerField(default=0)
    fours = models.IntegerField(default=0)
    sixes = models.IntegerField(default=0)
    strike_rate = models.FloatField(default=0)

    wicket_info = models.CharField(max_length=255, blank=True, default="")
    dismissal_type = models.CharField(max_length=50, blank=True, default="")
    fielder_name = models.CharField(max_length=100, blank=True, default="")
    is_out = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.player_name} - {self.match} - Inn {self.innings}"


class PlayerStat(models.Model):
    name = models.CharField(max_length=100)
    team = models.CharField(max_length=100, blank=True, default="")

    runs = models.IntegerField(default=0)
    balls = models.IntegerField(default=0)
    wickets = models.IntegerField(default=0)

    fours = models.IntegerField(default=0)
    sixes = models.IntegerField(default=0)
    economy = models.FloatField(default=0)

    strike_rate = models.FloatField(default=0)


class PointsTableEntry(models.Model):
    team = models.CharField(max_length=100, unique=True)
    played = models.IntegerField(default=0)
    won = models.IntegerField(default=0)
    lost = models.IntegerField(default=0)
    tied = models.IntegerField(default=0)
    no_result = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    net_run_rate = models.FloatField(default=0)

    class Meta:
        ordering = ["-points", "-net_run_rate", "team"]

    def __str__(self):
        return self.team

class Commentary(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    over_text = models.CharField(max_length=10)
    event = models.CharField(max_length=20)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.match} - {self.over_text} - {self.event}"


class TeamPlayer(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.CharField(max_length=100)
    player_name = models.CharField(max_length=100)
    role = models.CharField(max_length=30, blank=True, default="")  # batter, bowler, all-rounder, keeper
    is_playing_xi = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.team} - {self.player_name}"

