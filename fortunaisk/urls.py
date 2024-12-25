# fortunaisk/urls.py

# Django
from django.urls import path

from .views import resolve_anomaly  # Assurez-vous que resolve_anomaly est importé
from .views import (
    admin_dashboard,
    create_auto_lottery,
    create_lottery,
    delete_auto_lottery,
    distribute_prize,
    edit_auto_lottery,
    list_auto_lotteries,
    lottery,
    lottery_detail,
    lottery_history,
    lottery_participants,
    terminate_lottery,
    ticket_purchases,
    user_dashboard,
    winner_list,
)

app_name = "fortunaisk"

urlpatterns = [
    path("lottery/", lottery, name="lottery"),
    path("winners/", winner_list, name="winner_list"),
    path("admin_dashboard/", admin_dashboard, name="admin_dashboard"),
    path("ticket_purchases/", ticket_purchases, name="ticket_purchases"),
    path("history/", lottery_history, name="lottery_history"),
    path("dashboard/", user_dashboard, name="user_dashboard"),
    path(
        "lottery/<int:lottery_id>/participants/",
        lottery_participants,
        name="lottery_participants",
    ),
    path("lottery_create/", create_lottery, name="lottery_create"),
    path("auto_lotteries/", list_auto_lotteries, name="auto_lottery_list"),
    path("auto_lotteries/create/", create_auto_lottery, name="auto_lottery_create"),
    path(
        "auto_lotteries/edit/<int:autolottery_id>/",
        edit_auto_lottery,
        name="auto_lottery_edit",
    ),
    path(
        "auto_lotteries/delete/<int:autolottery_id>/",
        delete_auto_lottery,
        name="auto_lottery_delete",
    ),
    path(
        "terminate_lottery/<int:lottery_id>/",
        terminate_lottery,
        name="terminate_lottery",
    ),
    path(
        "resolve_anomaly/<int:anomaly_id>/",
        resolve_anomaly,
        name="resolve_anomaly",
    ),
    path(
        "distribute_prize/<int:winner_id>/",
        distribute_prize,
        name="distribute_prize",
    ),
    path(
        "lottery/<int:lottery_id>/detail/",
        lottery_detail,
        name="lottery_detail",
    ),
]
