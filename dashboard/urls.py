from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('matches/', views.matches_page, name='matches'),
    path('player-stats/', views.player_stats_page, name='player_stats_page'),
    path('points-table/', views.points_table_page, name='points_table_page'),
    path('scorecard/', views.scorecard_page, name='scorecard_page'),

    path('get-score/', views.get_score, name='get_score'),
    path('players-api/', views.players_api, name='players_api'),
    path('player-stats-api/', views.player_stats_api, name='player_stats_api'),
    path('points-table-api/', views.points_table_api, name='points_table_api'),
    path('commentary-api/', views.commentary_api, name='commentary_api'),
    path('over-data/', views.over_data, name='over_data'),
    path('chart-data/', views.chart_data, name='chart_data'),
]