from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import JsonResponse
from django.urls import Resolver404, resolve, reverse
from django.utils.cache import patch_cache_control


class ApprovedAccessMiddleware:
    public_views = {"login", "register", "logout", "admin:login", "admin:logout"}
    public_asset_extensions = {".css", ".js", ".woff", ".woff2", ".ttf", ".eot"}

    def __init__(self, get_response):
        self.get_response = get_response
        images = {"images/logo.png", "images/icons.svg"}
        hashed = getattr(staticfiles_storage, "hashed_files", {})
        self.public_images = images | {
            hashed.get(image, image).replace("\\", "/") for image in images
        }

    def is_public_asset(self, path):
        prefix = urlsplit(settings.STATIC_URL).path
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        if not path.startswith(prefix):
            return False
        relative = path[len(prefix):]
        parts = PurePosixPath(relative).parts
        if ".." in parts or "\\" in relative:
            return False
        return (
            PurePosixPath(relative).suffix.lower() in self.public_asset_extensions
            or relative in self.public_images
            or relative.startswith("admin/img/")
        )

    def __call__(self, request):
        public_asset = self.is_public_asset(request.path_info)
        if not public_asset and not (
            request.user.is_authenticated and request.user.is_active
        ):
            try:
                public_view = resolve(request.path_info).view_name in self.public_views
            except Resolver404:
                public_view = False
            if not public_view:
                if "application/json" in request.headers.get("Accept", ""):
                    response = JsonResponse({
                        "ok": False,
                        "message": "Для доступу увійдіть до схваленого облікового запису.",
                        "login_url": reverse("login"),
                    }, status=401)
                else:
                    response = redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
                patch_cache_control(response, private=True, no_store=True, max_age=0)
                return response
        response = self.get_response(request)
        if not public_asset:
            patch_cache_control(response, private=True, no_store=True, max_age=0)
        return response
