from django.urls import path

from . import auth_views, views

app_name = "agentkit"

urlpatterns = [
    path("auth/csrf/", auth_views.csrf, name="csrf"),
    path("auth/login/", auth_views.login_view, name="login"),
    path("auth/logout/", auth_views.logout_view, name="logout"),
    path("auth/me/", auth_views.me, name="me"),
    path("capabilities/", views.capabilities, name="capabilities"),
    path("sessions/", views.sessions, name="sessions"),
    path("sessions/<uuid:session_id>/", views.session_detail, name="session-detail"),
    path("sessions/<uuid:session_id>/messages/stream/", views.message_stream, name="message-stream"),
    path("actions/<uuid:proposal_id>/confirm/", views.proposal_confirm, name="proposal-confirm"),
    path("actions/<uuid:proposal_id>/cancel/", views.proposal_cancel, name="proposal-cancel"),
]
