# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class FortunaiskMenu(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            "Fortunaisk",
            "fas fa-ticket-alt fa-fw",
            "fortunaisk:lottery",
            navactive=["fortunaisk:lottery"],
        )

    def render(self, request):
        if request.user.has_perm("fortunaisk.view_ticket"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return FortunaiskMenu()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "fortunaisk", r"^fortunaisk/")
