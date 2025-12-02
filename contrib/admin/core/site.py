# -*- coding: utf-8 -*-
"""
site

Core admin site implementation and registration utilities.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from tortoise.exceptions import IntegrityError
from tortoise.models import Model
from config.settings import settings

from ..adapters.tortoise import get_model_descriptor

from .auth import (
    AdminUserDTO,
    build_auth_router,
    get_current_admin_user,
    require_permissions,
)
from .permissions import require_global_permission, PermAction
from .base import BaseModelAdmin
from .pages import FreeViewPage, SettingsPage
from .settings import SettingsKey, system_config
from .registry import PageRegistry, MenuItem
from ..models.content_type import AdminContentType
from ..crud import CrudRouterBuilder
from ..api import API_PREFIX, router as api_router
from ..provider import TemplateProvider

logger = logging.getLogger(__name__)



class AdminSite:
    """Admin registry: models, pages and menus."""

    def __init__(self, *, title: str | None = None, templates: Jinja2Templates | None = None) -> None:
        """Initialize the admin site with optional title and templates."""
        if title is None:
            title = system_config.get_cached(
                SettingsKey.DEFAULT_ADMIN_TITLE, "Admin"
            )
        self.title = title
        # key: (app_label, model_slug) in lowercase
        self.model_reg: Dict[tuple[str, str], BaseModelAdmin] = {}
        self.registry = PageRegistry()
        self.templates = templates
        # in-process map: (app.lower(), model.lower()) -> ct_id
        self.ct_map: Dict[tuple[str, str], int] = {}

    # ==== Registration ====
    def register(
        self,
        app: str,
        model: type[Model],
        admin_cls: type,
        *,
        settings: bool = False,
        icon: str | None = None,
    ) -> None:
        """Register a model admin.

        Args:
            app: application label, e.g. "streams"
            model: Tortoise ORM model class
            admin_cls: admin class for this model
            settings: register under /settings (True) or /orm (False)
            icon: Bootstrap icon class for menu (e.g. "bi-gear")
        """
        app_label = app
        model_cls = model
        model_slug = model_cls.__name__.lower()

        if admin_cls is None:
            raise ValueError("Admin class is required")

        # Support both admin initializers:
        #   AdminClass(self, app_label, model_slug)   — new style
        #   AdminClass(model_cls)                     — old style
        try:
            admin = admin_cls(self, app_label, model_slug)
        except TypeError:
            admin = admin_cls(model_cls)
            setattr(admin, "app_label", app_label)
            setattr(admin, "model_slug", model_slug)
        display_name = admin.get_verbose_name_plural()

        self.model_reg[(app_label.lower(), model_slug.lower())] = admin
        self.registry.register_view_entry(
            app=app_label,
            model=model_slug,           # store slug in registry
            admin_cls=admin_cls,
            settings=settings,
            icon=icon,
            name=display_name,
        )

    def register_both(
        self,
        app: str,
        model: type[Model],
        admin_cls: type,
        *,
        icon: str | None = None,
    ) -> None:
        """Register the admin in both ORM and Settings modes."""
        self.register(app=app, model=model, admin_cls=admin_cls, settings=False, icon=icon)
        self.register(app=app, model=model, admin_cls=admin_cls, settings=True, icon=icon)

    def all_models(self) -> List[tuple[str, str]]:
        """Return list of registered (app, model) pairs."""
        return list(self.model_reg.keys())

    def find_admin_or_404(self, app: str, model: str) -> BaseModelAdmin:
        """Return admin for given model or raise 404."""
        admin = self.model_reg.get((app.lower(), model.lower()))
        if not admin:
            raise HTTPException(status_code=404, detail="Unknown admin model")
        return admin

    async def finalize(self) -> None:
        """Idempotent upsert of ContentType records for registered models."""
        for app, model in self.model_reg.keys():
            dotted = f"{app}.{model}"
            ct = await AdminContentType.get_or_none(app_label=app, model=model)
            if ct is None:
                try:
                    ct = await AdminContentType.create(app_label=app, model=model, dotted=dotted)
                except IntegrityError:
                    ct = await AdminContentType.get(app_label=app, model=model)
            elif ct.dotted != dotted:
                ct.dotted = dotted
                await ct.save()
            self.ct_map[(app.lower(), model.lower())] = ct.id

    def get_ct_id(self, app: str, model: str) -> int | None:
        """Return ct_id for (app, model) or ``None`` if not registered."""
        return self.ct_map.get((app.lower(), model.lower()))

    def parse_section_path(self, request: Request) -> tuple[bool, str | None, str | None]:
        """Extract section info from ``request.url.path``.

        The returned tuple consists of ``(is_settings, app_label, model_slug)``.
        ``is_settings`` is ``True`` when the path points to the settings section,
        otherwise ``False``. ``app_label`` and ``model_slug`` are extracted from
        ``/orm/<app>/<model>/`` or ``/settings/<app>/<model>/`` URLs. When the
        path does not include app/model parts they are returned as ``None``.
        """

        path = request.url.path
        prefix = settings.ADMIN_PATH.rstrip("/")
        if prefix and path.startswith(prefix):
            path = path[len(prefix) :]

        is_settings = False
        app_label: str | None = None
        model_slug: str | None = None
        base: str | None = None

        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")

        if path.startswith(settings_prefix + "/") or path == settings_prefix:
            is_settings = True
            base = settings_prefix
        elif path.startswith(orm_prefix + "/") or path == orm_prefix:
            base = orm_prefix

        if base is not None:
            tail = path[len(base) :]
            if tail.startswith("/"):
                tail = tail[1:]
            parts = tail.split("/", 2)
            if len(parts) >= 1 and parts[0]:
                app_label = parts[0]
            if len(parts) >= 2 and parts[1]:
                model_slug = parts[1]

        return is_settings, app_label, model_slug

    @staticmethod
    def _format_app_label(app_label: str) -> str:
        display_label = app_label.replace("_", "\u00A0")
        if display_label:
            display_label = display_label[0].upper() + display_label[1:]
        return display_label

    
    def get_sidebar_apps(self, *, settings: bool) -> List[tuple[str, List[Dict[str, Any]]]]:
        apps: Dict[str, List[Dict[str, Any]]] = {}
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        for entry in self.registry.view_entries:
            if settings and not entry.settings:
                continue
            if not settings and entry.settings:
                continue
            arr = apps.setdefault(entry.app, [])
            admin = self.model_reg.get((entry.app.lower(), entry.model.lower()))
            display = (
                admin.get_verbose_name_plural()
                if admin is not None
                else entry.name or entry.model.replace("_", " ").title()
            )
            arr.append(
                {
                    "model_name": entry.model,
                    "display_name": display,
                    "path": (settings_prefix if entry.settings else orm_prefix)
                    + f"/{entry.app}/{entry.model}",
                    "icon": entry.icon,
                    "settings": entry.settings,
                }
            )
        out: List[tuple[str, List[Dict[str, Any]]]] = []
        for app_label, models in apps.items():
            models.sort(key=lambda m: m["display_name"].lower())
            out.append((app_label, models))
        out.sort(key=lambda x: x[0].lower())
        return out

    def build_template_ctx(
        self,
        request: Request,
        user: AdminUserDTO | None,
        *,
        page_title: str | None = None,
        app_label: str | None = None,
        model_name: str | None = None,
        is_settings: bool | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Build base template context for admin pages."""
        if is_settings is None or app_label is None or model_name is None:
            parsed_is_settings, parsed_app, parsed_model = self.parse_section_path(request)
            if is_settings is None:
                is_settings = parsed_is_settings
            if app_label is None:
                app_label = parsed_app
            if model_name is None:
                model_name = parsed_model
        raw_apps = self.get_sidebar_apps(settings=is_settings)
        apps = [
            {
                "label": a_label,
                "display": self._format_app_label(a_label),
                "models": models,
            }
            for a_label, models in raw_apps
        ]
        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
        ctx: Dict[str, Any] = {
            "request": request,
            "user": user,
            "site_title": self.title,
            "prefix": settings.ADMIN_PATH,
            "ORM_PREFIX": orm_prefix,
            "SETTINGS_PREFIX": settings_prefix,
            "VIEWS_PREFIX": views_prefix,
            "apps": apps,
            "current_app": app_label,
            "current_model": model_name,
            "section_mode": "settings" if is_settings else "orm",
            "assets": {"css": [], "js": []},
        }
        if page_title is not None:
            ctx["page_title"] = page_title
        if extra:
            ctx.update(extra)

        # Collect form widget assets for add/edit pages
        last_segment = request.url.path.rstrip("/").split("/")[-1]
        if last_segment in {"add", "edit"} and app_label and model_name:
            admin = self.model_reg.get((app_label.lower(), model_name.lower()))
            if admin is not None:
                md = get_model_descriptor(admin.model)
                ctx["assets"] = admin.collect_assets(
                    md, mode=last_segment, obj=None, request=request
                )
        return ctx

    def register_view(self, *, path: str, name: str, icon: str | None = None):
        """Register a simple view page handled by ``func``."""

        def decorator(func: Callable[..., Any]):
            page = FreeViewPage(title=name, path=path, icon=icon, handler=func)
            self.registry.page_list.append(page)
            self.registry.menu_list.append(
                MenuItem(title=name, path=path, icon=icon)
            )
            return func
        return decorator

    def register_settings(self, *, path: str, name: str, icon: str | None = None):
        """Register a settings page handled by ``func``."""
        page_type_settings = system_config.get_cached(SettingsKey.PAGE_TYPE_SETTINGS, "settings")

        def decorator(func: Callable[..., Any]):
            page = SettingsPage(title=name, path=path, icon=icon, handler=func)
            self.registry.page_list.append(page)
            self.registry.menu_list.append(
                MenuItem(title=name, path=path, icon=icon, page_type=page_type_settings)
            )
            return func
        return decorator

    # ==== Router ====
    def build_router(self, template_provider: TemplateProvider) -> APIRouter:
        router = APIRouter()
        templates = self.templates or template_provider.get_templates()
        setattr(router, "templates", templates)

        def get_admin_api() -> dict[str, str]:
            """Expose fully-qualified API paths for templates."""

            api_prefix = system_config.get_cached(SettingsKey.API_PREFIX, "/api")
            schema_path = system_config.get_cached(
                SettingsKey.API_SCHEMA, f"{api_prefix}/schema"
            )
            list_filters_path = system_config.get_cached(
                SettingsKey.API_LIST_FILTERS, f"{api_prefix}/list_filters"
            )
            base = settings.ADMIN_PATH.rstrip("/")

            return {
                "prefix": f"{base}{api_prefix}",
                "schema": f"{base}{schema_path}",
                "list_filters": f"{base}{list_filters_path}",
            }

        templates.env.globals.update(
            iter_settings_entries=self.registry.iter_settings,
            iter_orm_entries=self.registry.iter_orm,
            get_admin_api=get_admin_api,
        )

        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
        page_type_settings = system_config.get_cached(SettingsKey.PAGE_TYPE_SETTINGS)

        self._attach_auth_routes(router, templates)
        self._attach_page_routes(
            router,
            templates,
            orm_prefix,
            settings_prefix,
            views_prefix,
            page_type_settings,
        )
        self._attach_api_routes(router)
        self._attach_crud_routes(router, orm_prefix, settings_prefix)

        return router

    def _attach_auth_routes(
        self, router: APIRouter, templates: Jinja2Templates
    ) -> None:
        router.include_router(build_auth_router(templates), tags=["admin-auth"])

    def _attach_page_routes(
        self,
        router: APIRouter,
        templates: Jinja2Templates,
        orm_prefix: str,
        settings_prefix: str,
        views_prefix: str,
        page_type_settings: str,
    ) -> None:
        @router.get("/", response_class=HTMLResponse)
        async def admin_index(
            request: Request,
            user: AdminUserDTO = Depends(require_permissions((), admin_site=self)),
        ) -> HTMLResponse:
            dash_title = await system_config.get(SettingsKey.DASHBOARD_PAGE_TITLE)
            return templates.TemplateResponse(
                "pages/index.html",
                {
                    "request": request,
                    "site_title": self.title,
                    "user": user,
                    "page_title": dash_title,
                    "prefix": settings.ADMIN_PATH,
                    "ORM_PREFIX": orm_prefix,
                    "SETTINGS_PREFIX": settings_prefix,
                    "VIEWS_PREFIX": views_prefix,
                },
            )

        for page in [p for p in self.registry.page_list if isinstance(p, FreeViewPage)]:
            user_dep = (
                get_current_admin_user
                if page.page_type == page_type_settings
                else require_permissions((), admin_site=self)
            )
            perm_dep = (
                require_global_permission(PermAction.view)
                if page.page_type == page_type_settings
                else (lambda: None)
            )

            async def view_handler(
                request: Request,
                page: FreeViewPage = Depends(lambda page=page: page),
                user: AdminUserDTO = Depends(user_dep),
                _: None = Depends(perm_dep),
            ) -> HTMLResponse:
                ctx: Dict[str, Any] = {}
                if page.handler:
                    res = page.handler(request=request, user=user)
                    if hasattr(res, "__await__"):
                        res = await res  # type: ignore
                    ctx = res or {}
                is_settings = (
                    page.page_type == page_type_settings
                    or page.path == settings_prefix
                )
                if page.path == orm_prefix:
                    template_name = "pages/orm.html"
                elif page.path == settings_prefix:
                    template_name = "pages/settings.html"
                elif page.path == views_prefix:
                    template_name = "pages/views.html"
                else:
                    template_name = "layout/default.html"
                base_ctx = self.build_template_ctx(
                    request,
                    user,
                    page_title=page.title,
                    is_settings=is_settings,
                    extra=ctx,
                )
                if page.path != views_prefix:
                    base_ctx["menu"] = self.registry.make_menu()
                return templates.TemplateResponse(template_name, base_ctx)

            router.add_api_route(
                page.path, view_handler, methods=["GET"], name=page.title
            )

    def _attach_api_routes(self, router: APIRouter) -> None:
        router.include_router(api_router, prefix=API_PREFIX)

    def _attach_crud_routes(
        self, router: APIRouter, orm_prefix: str, settings_prefix: str
    ) -> None:
        for entry in self.registry.iter_orm():
            prefix = f"{orm_prefix}/{entry.app}/{entry.model}"
            CrudRouterBuilder.mount(
                router,
                admin_site=self,
                prefix=prefix,
                admin_cls=entry.admin_cls,
                perms="model",
                app_label=entry.app,
                model_name=entry.model,
            )

        for entry in self.registry.iter_settings():
            prefix = f"{settings_prefix}/{entry.app}/{entry.model}"
            CrudRouterBuilder.mount(
                router,
                admin_site=self,
                prefix=prefix,
                admin_cls=entry.admin_cls,
                perms="global",
                app_label=entry.app,
                model_name=entry.model,
            )

        self.registry.make_menu()

# The End
