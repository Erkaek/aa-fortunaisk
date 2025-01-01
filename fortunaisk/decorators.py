# fortunaisk/decorators.py

# Django
from django.core.exceptions import PermissionDenied


def permission_required(permission_codename):
    """
    Decorator for views that checks whether a user has a specific permission.
    """

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if (
                request.user.has_perm(f"fortunaisk.{permission_codename}")
                or request.user.is_superuser
            ):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied

        return _wrapped_view

    return decorator


def can_access_app(view_func):
    """
    Decorator for views that checks whether a user has the "can_access_app" permission.
    """

    return permission_required("can_access_app")(view_func)


def can_admin_app(view_func):
    """
    Decorator for views that checks whether a user has the "can_admin_app" permission
    """
    return permission_required("can_admin_app")(view_func)
