# Django
from django.urls import path

from . import views

app_name = "fortunaisk"

urlpatterns = [
    path("lottery/", views.lottery, name="lottery"),
    path("winners/", views.winner_list, name="winner_list"),
    path("admin/", views.admin_dashboard, name="admin"),
]
