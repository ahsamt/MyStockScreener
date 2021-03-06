from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name="index"),
    path("watchlist", views.watchlist, name="watchlist"),
    path("backtester", views.backtester, name="backtester"),
    path("about", views.about, name="about"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path('graph/<int:ticker_id>-<int:constructor_id>', views.display_graph, name="display_graph"),


    # API Routes
    path("saved_searches", views.saved_searches, name="saved_searches"),
    path("saved_searches/<int:search_id>", views.saved_search, name="saved_search"),
    path("saved_signals", views.saved_signals, name="saved_signals")
]
