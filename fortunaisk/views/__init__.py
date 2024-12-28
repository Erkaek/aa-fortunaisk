# fortunaisk/views/__init__.py

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
    resolve_anomaly,
    terminate_lottery,
    ticket_purchases,
    user_dashboard,
    winner_list,
)

__all__ = [
    "admin_dashboard",
    "resolve_anomaly",
    "distribute_prize",
    "list_auto_lotteries",
    "create_auto_lottery",
    "edit_auto_lottery",
    "delete_auto_lottery",
    "lottery",
    "ticket_purchases",
    "winner_list",
    "lottery_history",
    "create_lottery",
    "lottery_detail",
    "lottery_participants",
    "terminate_lottery",
    "user_dashboard",
]
