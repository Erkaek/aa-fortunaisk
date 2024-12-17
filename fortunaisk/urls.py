# fortunaisk/urls.py

# Django
from django.urls import path

from . import views

app_name = "fortunaisk"

urlpatterns = [
    path("lottery/", views.lottery, name="lottery"),
    path("winners/", views.winner_list, name="winner_list"),
    path("admin/", views.admin_dashboard, name="admin_dashboard"),
    path("ticket_purchases/", views.ticket_purchases, name="ticket_purchases"),
    path("select_winner/", views.select_winner, name="select_winner"),
    path("history/", views.lottery_history, name="lottery_history"),
    path("dashboard/", views.user_dashboard, name="user_dashboard"),
    path(
        "lottery/<int:lottery_id>/participants/",
        views.lottery_participants,
        name="lottery_participants",
    ),
]
