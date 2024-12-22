# fortunaisk/views/__init__.py

from .admin_views import admin_dashboard
from .autolottery_views import (
    create_auto_lottery,
    delete_auto_lottery,
    edit_auto_lottery,
    list_auto_lotteries,
)
from .lottery_views import (
    lottery,
    lottery_history,
    lottery_participants,
    terminate_lottery,
    ticket_purchases,
    winner_list,
)
from .user_views import user_dashboard

__all__ = [
    "admin_dashboard",
    "list_auto_lotteries",
    "create_auto_lottery",
    "edit_auto_lottery",
    "delete_auto_lottery",
    "lottery",
    "lottery_participants",
    "ticket_purchases",
    "winner_list",
    "lottery_history",
    "terminate_lottery",
    "user_dashboard",
]