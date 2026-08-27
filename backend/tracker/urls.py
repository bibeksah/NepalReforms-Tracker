from django.urls import path

from . import views

urlpatterns = [
    path("api/public/agendas/graph-status/", views.public_agenda_graph_status, name="public_agenda_graph_status"),
]
