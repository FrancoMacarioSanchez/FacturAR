from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from billing import views as billing_views
urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    path("", include("tenant.urls")),
    path("billing/", include("billing.urls")),
    path("arca/", include("arca_gateway.urls")),
    path("api/v1/", include("api.urls")),
    path("", billing_views.dashboard, name="dashboard"),
    path("users/", include("users.urls", namespace="users")),
]