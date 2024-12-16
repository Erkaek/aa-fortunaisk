"""App URLs"""

# Django
from django.urls import path

# AA fortunaisk App
from fortunaisk import views

app_name: str = "fortunaisk"

urlpatterns = [
    path("", views.index, name="index"),
]
