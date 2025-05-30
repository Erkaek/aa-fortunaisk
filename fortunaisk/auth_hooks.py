# fortunaisk/auth_hooks.py
"""
Alliance Auth hooks for integrating FortunaIsk into the Alliance Auth platform.

This module defines the integration points between FortunaIsk and Alliance Auth,
including navigation menu entries, URL patterns, and permission checks.
"""

# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class FortunaIskMenu(MenuItemHook):
    """
    Adds a menu item for FortunaIsk in the Alliance Auth navigation.

    This menu item is dynamically shown or hidden based on user permissions,
    providing access to the lottery system for authorized users.
    """

    def __init__(self):
        """
        Initialize the FortunaIsk menu entry.

        Sets up the menu with the proper name, icon, URL, and active navigation patterns.
        """
        super().__init__(
            "Fortuna-ISK",
            "fas fa-ticket-alt fa-fw",
            "fortunaisk:lottery",
            navactive=["fortunaisk:lottery"],
        )

    def render(self, request):
        """
        Conditionally render the menu item based on user permissions.

        Args:
            request: The HTTP request object containing the current user

        Returns:
            str: The rendered HTML for the menu item, or an empty string if
                the user lacks necessary permissions
        """
        if request.user.has_perm("fortunaisk.can_access_app") or request.user.has_perm(
            "fortunaisk.can_admin_app"
        ):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    """
    Register the FortunaIsk menu item with Alliance Auth.

    This hook is automatically discovered and called by Alliance Auth
    during application initialization.

    Returns:
        FortunaIskMenu: An instance of the menu item
    """
    return FortunaIskMenu()


@hooks.register("url_hook")
def register_urls():
    """
    Register FortunaIsk URL patterns with Alliance Auth.

    This hook is automatically discovered and called by Alliance Auth
    during application initialization, making FortunaIsk's views accessible
    under the /fortunaisk/ URL path.

    Returns:
        UrlHook: A URL hook configured with FortunaIsk's URL patterns
    """
    return UrlHook(urls, "fortunaisk", r"^fortunaisk/")
