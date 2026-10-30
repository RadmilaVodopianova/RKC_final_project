from django.contrib import admin
from django.urls import include, path, re_path

from accounts.views import private_media

urlpatterns = [
    re_path(r"^media/(?P<path>.*)$", private_media, name="private_media"),
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("orders.urls")),
]
