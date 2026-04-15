from django.contrib import admin

from .models import BallHistory, CurrentPlayers, Match, PlayerStat, PointsTableEntry


admin.site.register(Match)
admin.site.register(BallHistory)
admin.site.register(CurrentPlayers)
admin.site.register(PlayerStat)
admin.site.register(PointsTableEntry)
