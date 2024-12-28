# fortunaisk/views/__init__.py

from .admin_views import admin_dashboard, distribute_prize, resolve_anomaly
from .autolottery_views import (
    create_auto_lottery,
    delete_auto_lottery,
    edit_auto_lottery,
    list_auto_lotteries,
)
from .lottery_views import (
    create_lottery,
    lottery,
    lottery_detail,
    lottery_history,
    lottery_participants,
    terminate_lottery,
    ticket_purchases,
    winner_list,
)
from .user_views import user_dashboard

__all__ = [
    "admin_dashboard",
    "resolve_anomaly",
    "distribute_prize",
    "create_auto_lottery",
    "list_auto_lotteries",
    "edit_auto_lottery",
    "delete_auto_lottery",
    "create_lottery",
    "lottery",
    "lottery_detail",
    "lottery_history",
    "lottery_participants",
    "terminate_lottery",
    "ticket_purchases",
    "winner_list",
    "user_dashboard",
]
