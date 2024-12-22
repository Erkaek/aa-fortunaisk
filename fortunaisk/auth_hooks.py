# fortunaisk/auth_hooks.py
"""
Alliance Auth hooks for adding FortunaIsk to the navigation menu.
"""

# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class FortunaIskMenu(MenuItemHook):
    """
    Adds a menu item for FortunaIsk in the Alliance Auth navigation,
    visible to users with the appropriate permissions.
    """

    def __init__(self):
        super().__init__(
            "FortunaIsk",
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
    return FortunaIskMenu()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "fortunaisk", r"^fortunaisk/")
