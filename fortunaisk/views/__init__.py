# fortunaisk/views/__init__.py

from .views import create_auto_lottery  # Importer la vue renommée
from .views import (
    admin_dashboard,
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
    "distribute_prize",
    "resolve_anomaly",
    "list_auto_lotteries",
    "create_auto_lottery",  # Inclure la vue renommée
    "edit_auto_lottery",
    "delete_auto_lottery",
    "lottery_detail",
    "create_lottery",
    "lottery",
    "lottery_history",
    "lottery_participants",
    "terminate_lottery",
    "ticket_purchases",
    "winner_list",
    "user_dashboard",
]
