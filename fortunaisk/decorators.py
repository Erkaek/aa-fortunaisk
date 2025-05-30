# fortunaisk/decorators.py

# Django
from django.core.exceptions import PermissionDenied


def permission_required(permission_codename):
    """
    Decorator for views that checks whether a user has a specific permission.

    This decorator evaluates whether the current user has the specified permission
    in the fortunaisk application namespace. If the permission check fails, it raises
    a PermissionDenied exception, which Django converts to an HTTP 403 Forbidden response.

    Args:
        permission_codename (str): The codename of the permission to check,
                                  without the 'fortunaisk.' prefix.

    Returns:
        callable: A decorator function that wraps the view function.

    Example:
        @permission_required('can_view_reports')
        def view_reports(request):
            # View logic here
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

    This decorator restricts access to regular users of the FortunaIsk application.
    It ensures that only users who have been granted basic access rights can view
    the decorated pages.

    Args:
        view_func (callable): The view function to be decorated.

    Returns:
        callable: The decorated view function that checks for the permission.

    Raises:
        PermissionDenied: If the user doesn't have the required permission.
    """
    return permission_required("can_access_app")(view_func)


def can_admin_app(view_func):
    """
    Decorator for views that checks whether a user has the "can_admin_app" permission.

    This decorator restricts access to administrative views of the FortunaIsk application.
    It ensures that only users who have been granted administrative rights can access
    the management features of the application.

    Args:
        view_func (callable): The view function to be decorated.

    Returns:
        callable: The decorated view function that checks for the permission.

    Raises:
        PermissionDenied: If the user doesn't have the required permission.
    """
    return permission_required("can_admin_app")(view_func)
