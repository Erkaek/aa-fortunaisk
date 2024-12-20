# fortunaisk/urls.py
"""URL routing for the FortunaIsk lottery application."""

# Django
from django.urls import path

from . import views

app_name = "fortunaisk"

urlpatterns = [
    path("lottery/", views.lottery, name="lottery"),
    path("winners/", views.winner_list, name="winner_list"),
    path("admin/", views.admin_dashboard, name="admin_dashboard"),
    path("ticket_purchases/", views.ticket_purchases, name="ticket_purchases"),
    path("select_winner/<int:lottery_id>/", views.select_winner, name="select_winner"),
    path("history/", views.lottery_history, name="lottery_history"),
    path("dashboard/", views.user_dashboard, name="user_dashboard"),
    path(
        "lottery/<int:lottery_id>/participants/",
        views.lottery_participants,
        name="lottery_participants",
    ),
    path(
        "lottery_create/", views.create_lottery, name="lottery_create"
    ),
    path("auto_lotteries/", views.list_auto_lotteries, name="auto_lottery_list"),
    path("auto_lotteries/create/", views.create_auto_lottery, name="auto_lottery_create"),
    path("auto_lotteries/edit/<int:autolottery_id>/", views.edit_auto_lottery, name="auto_lottery_edit"),
    path("auto_lotteries/delete/<int:autolottery_id>/", views.delete_auto_lottery, name="auto_lottery_delete"),# nouvelle URL
]
