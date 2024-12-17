# fortunaisk/auth_hooks.py

# Django
from django.contrib.auth.models import User

# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class FortunaiskMenu(MenuItemHook):
    def __init__(self):
        super().__init__(
            "Fortunaisk",
            "fas fa-ticket-alt fa-fw",
            "fortunaisk:lottery",
            navactive=["fortunaisk:lottery"],
        )

    def render(self, request):
        if request.user.has_perm("fortunaisk.view_ticketpurchase"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return FortunaiskMenu()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "fortunaisk", r"^fortunaisk/")
