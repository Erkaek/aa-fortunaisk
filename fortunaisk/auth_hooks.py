# fortunaisk/auth_hooks.py
"""Alliance Auth hooks pour ajouter FortunaIsk au menu de navigation."""

# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class FortunaiskMenu(MenuItemHook):
    """Ajoute un élément de menu pour FortunaIsk dans la navigation d'Alliance Auth, visible pour les utilisateurs avec les permissions appropriées."""

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
    return FortunaiskMenu()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "fortunaisk", r"^fortunaisk/")
