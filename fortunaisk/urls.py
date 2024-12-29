# Django
from django.urls import path

from .views import (
    admin_dashboard,
    anomalies_list,
    create_auto_lottery,
    create_lottery,
    delete_auto_lottery,
    distribute_prize,
    edit_auto_lottery,
    lottery,
    lottery_detail,
    lottery_history,
    lottery_participants,
    resolve_anomaly,
    terminate_lottery,
    user_dashboard,
    winner_list,
)

app_name = "fortunaisk"

urlpatterns = [
    # User-facing
    path("lottery/", lottery, name="lottery"),
    path("dashboard/", user_dashboard, name="user_dashboard"),
    # Winners & history
    path("winners/", winner_list, name="winner_list"),
    path("history/", lottery_history, name="lottery_history"),
    # Admin Dashboard
    path("admin_dashboard/", admin_dashboard, name="admin_dashboard"),
    # Standard Lottery
    path("lottery_create/", create_lottery, name="lottery_create"),
    path(
        "lottery/<int:lottery_id>/participants/",
        lottery_participants,
        name="lottery_participants",
    ),
    path(
        "lottery/<int:lottery_id>/detail/",
        lottery_detail,
        name="lottery_detail",
    ),
    path(
        "terminate_lottery/<int:lottery_id>/",
        terminate_lottery,
        name="terminate_lottery",
    ),
    # AutoLottery
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
    # Anomaly & Prize distribution
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
    path("anomalies/", anomalies_list, name="anomalies_list"),
]
