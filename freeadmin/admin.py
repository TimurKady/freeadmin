# -*- coding: utf-8 -*-
"""
site

Core admin site implementation and registration utilities.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, TYPE_CHECKING

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException, Form, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from importlib import import_module

from freeadmin.config import FreeAdminSettings, current_settings

from freeadmin.contrib.adapters import BaseAdapter
from freeadmin.core.interface.services.auth import AdminUserDTO
from freeadmin.core.interface.auth import admin_auth_service
from freeadmin.core.interface.permissions import permission_checker
from freeadmin.core.interface.services.permissions import (
    PermAction,
    PermissionsService,
    permissions_service,
)
from freeadmin.core.interface.base import BaseModelAdmin
from freeadmin.core.interface.pages import FreeViewPage, SettingsPage, PageDescriptorManager
from freeadmin.core.interface.settings import SettingsKey, system_config
from freeadmin.core.interface.registry import CardEntry, PageRegistry
from freeadmin.core.interface.sidebar import SidebarBuilder
from freeadmin.core.interface.context import TemplateContextBuilder
from freeadmin.core.interface.exceptions import AdminModelNotFound, PermissionDenied
from freeadmin.contrib.crud import CrudRouterBuilder
from freeadmin.contrib.api.cards import router as card_router
from freeadmin.core.interface.services.export import ExportService
from freeadmin.core.interface.services import ScopeQueryService, ScopeTokenService
from freeadmin.utils.icon import IconPathMixin
from freeadmin.core.interface.cards import CardManager
from freeadmin.core.interface.menu import MenuBuilder, PublicMenuBuilder
from freeadmin.core.interface.cache import SQLiteCardCache
from freeadmin.core.interface.cache.menu import MainMenuCache
from freeadmin.core.interface.permissions.checker import PermissionChecker
from freeadmin.utils.migration_errors import MigrationErrorClassifier

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from freeadmin.core.interface.permissions.checker import (
        PermissionChecker as PermissionCheckerType,
    )
    from freeadmin.core.runtime.provider import TemplateProvider

ImportService = import_module(
    "freeadmin.core.interface.services.import"
).ImportService

Model = Any

logger = logging.getLogger(__name__)

class AdminSite(IconPathMixin):
    """Admin registry: models, pages and menus."""

    def __init__(
        self,
        adapter: BaseAdapter,
        *,
        title: str | None = None,
        templates: Jinja2Templates | None = None,
        settings: FreeAdminSettings | None = None,
        permission_service: PermissionsService | None = None,
        permission_checker_obj: "PermissionCheckerType | None" = None,
        card_cache_class: type[SQLiteCardCache] | None = None,
        card_cache: SQLiteCardCache | None = None,
    ) -> None:
        """Initialize the admin site with required adapter."""
        self.adapter = adapter
        self.AdminContentType = adapter.content_type_model
        self.IntegrityError = getattr(adapter, "IntegrityError", Exception)
        self._title_override = title
        self._settings = settings or current_settings()
        self._permissions_service = permission_service or permissions_service
        # key: (app_label, model_slug) in lowercase
        self.model_reg: Dict[tuple[str, str], BaseModelAdmin] = {}
        self.registry = PageRegistry()
        self.menu_cache = MainMenuCache()
        self.menu_builder = MenuBuilder(self.registry, cache=self.menu_cache)
        self.public_menu_builder = PublicMenuBuilder()
        self.templates = templates
        # in-process map: dotted content type -> ct_id
        self.ct_map: Dict[str, int] = {}
        self._import_service = ImportService()
        self.pages = PageDescriptorManager(self)
        cache_factory = card_cache_class or SQLiteCardCache
        cache_path = getattr(self._settings, "event_cache_path", ":memory:")
        self.card_cache = card_cache or cache_factory(path=cache_path)
        self.cards = CardManager(
            self.registry,
            settings=self._settings,
            card_cache=self.card_cache,
        )
        self._migration_error_classifier = MigrationErrorClassifier()
        if permission_checker_obj is not None:
            self.permission_checker = permission_checker_obj
        elif permission_service is not None:
            self.permission_checker = PermissionChecker(self._permissions_service)
        else:
            self.permission_checker = permission_checker
        self._dashboard_virtual = self.registry.register_view_virtual(
            path="/",
            app_label="admin",
            slug_source="dashboard",
        )
        self._anonymous_card_cache_key = "anonymous"
        self._register_permission_invalidation_hook()

    @property
    def title(self) -> str:
        """Return configured admin site title."""
        if self._title_override is not None:
            return self._title_override
        return system_config.get_cached(
            SettingsKey.DEFAULT_ADMIN_TITLE, self._settings.admin_site_title
        )

    @property
    def brand_icon(self) -> str:
        """Return URL to the brand icon."""
        icon_path = system_config.get_cached(
            SettingsKey.BRAND_ICON, self._settings.brand_icon
        )
        prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, self._settings.admin_path
        )
        static_segment = system_config.get_cached(
            SettingsKey.STATIC_URL_SEGMENT, self._settings.static_url_segment
        )
        return self._resolve_icon_path(icon_path, prefix, static_segment)

    def get_locale(self, request: Request | None = None) -> str:
        """Return locale token derived from ``request`` headers or defaults."""

        if request is not None:
            header = request.headers.get("accept-language")
            if header:
                candidate = header.split(",", 1)[0].strip()
                if candidate:
                    return candidate
        return str(system_config.get_cached(SettingsKey.DEFAULT_LOCALE, "en"))

    @staticmethod
    def _model_to_slug(name: str) -> str:
        """Return lowercase model name as slug without regex."""
        return name.lower()

    def _register_permission_invalidation_hook(self) -> None:
        """Subscribe to permission cache invalidation events."""

        register = getattr(self.permission_checker, "register_user_invalidation_hook", None)
        if not callable(register):
            return
        try:
            register(self._handle_permission_invalidation)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to register permission invalidation hook")

    def _handle_permission_invalidation(self, user_id: str) -> None:
        """Drop cached card payloads associated with ``user_id``."""

        if not user_id or self.card_cache is None:
            return
        try:
            self.card_cache.invalidate_user(str(user_id))
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to invalidate card cache for user %s", user_id)

    def _resolve_card_cache_key(self, user: Any | None) -> str:
        """Return cache key representing ``user`` or anonymous fallback."""

        if user is None:
            return self._anonymous_card_cache_key
        identifier = getattr(user, "id", None)
        if identifier is None:
            return self._anonymous_card_cache_key
        return str(identifier)

    def _clear_card_cache(self) -> None:
        """Remove all cached card payloads."""

        if self.card_cache is None:
            return
        try:
            self.card_cache.clear()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to clear cached card entries")

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
            model: ORM model class
            admin_cls: admin class for this model
            settings: register under /settings (True) or /orm (False)
            icon: Bootstrap icon class for menu (e.g. "bi-gear")
        """
        app_label = app
        model_cls = model
        model_slug = self._model_to_slug(model_cls.__name__)

        if admin_cls is None:
            raise ValueError("Admin class is required")

        # Support both admin initializers:
        #   AdminClass(self, app_label, model_slug, adapter)   — new style
        #   AdminClass(model_cls, adapter)                     — old style
        try:
            admin = admin_cls(self, app_label, model_slug, self.adapter)
        except TypeError:
            admin = admin_cls(model_cls, self.adapter)
            setattr(admin, "app_label", app_label)
        display_name = admin.get_verbose_name_plural()

        self.model_reg[(app_label.lower(), model_slug.lower())] = admin
        self.registry.register_view_entry(
            app=app_label,
            model=model_slug,  # store slug in registry
            admin_cls=admin_cls,
            settings=settings,
            icon=icon,
            name=display_name,
        )
        self.menu_builder.invalidate_main_menu()

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

    def register_card(
        self,
        key: str,
        title: str,
        template: str,
        app: str | None = None,
        icon: str | None = None,
        channel: str | None = None,
        *,
        col_class: str = "col-2",
        scripts: List[str] | None = None,
        styles: List[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Register a card and expose it to the admin API.

        Accepts either ``app`` or ``label`` to group the card in navigation.
        Optional ``scripts`` and ``styles`` describe asset dependencies that
        will be aggregated for template rendering. ``col_class`` controls the
        Bootstrap column width applied to the dashboard grid.
        """

        label = kwargs.pop("label", None)
        if kwargs:
            unexpected = ", ".join(sorted(kwargs.keys()))
            raise TypeError(f"Unexpected keyword arguments: {unexpected}")
        app_label = app or label
        if app_label is None:
            raise ValueError("Either 'app' or 'label' must be provided for card registration")
        normalized_scripts = list(scripts or [])
        default_script = "cards/card.js"
        if default_script not in normalized_scripts:
            normalized_scripts.insert(0, default_script)
        normalized_styles = list(styles or [])
        self.cards.register_card(
            key=key,
            app=app_label,
            title=title,
            template=template,
            icon=icon,
            channel=channel,
            col_class=col_class,
            scripts=normalized_scripts,
            styles=normalized_styles,
        )
        self._clear_card_cache()

    def all_models(self) -> List[tuple[str, str]]:
        """Return list of registered (app, model) pairs."""
        return list(self.model_reg.keys())

    def find_admin_or_404(self, app: str, model: str) -> BaseModelAdmin:
        """Return admin for given model or raise 404."""
        admin = self.model_reg.get((app.lower(), model.lower()))
        if not admin:
            raise AdminModelNotFound("Unknown admin model")
        return admin

    async def finalize(self) -> None:
        """Idempotent upsert of ContentType records for models, cards and views."""

        async def _ensure_content_type(
            app_label: str, model_value: str, dotted: str
        ) -> None:
            ct = await self.adapter.get_or_none(self.AdminContentType, dotted=dotted)
            if ct is None:
                ct = self.AdminContentType(
                    app_label=app_label, model=model_value, dotted=dotted
                )
                try:
                    await self.adapter.save(ct)
                except self.IntegrityError:
                    ct = await self.adapter.get(
                        self.AdminContentType, dotted=dotted
                    )
            updated = False
            if ct.app_label != app_label:
                ct.app_label = app_label
                updated = True
            if ct.model != model_value:
                ct.model = model_value
                updated = True
            if ct.dotted != dotted:
                ct.dotted = dotted
                updated = True
            if not getattr(ct, "is_registered", True):
                ct.is_registered = True
                updated = True
            if updated:
                await self.adapter.save(ct)
            self.ct_map[dotted] = ct.id

        self.ct_map.clear()
        seen: set[str] = set()

        try:
            for app, model in self.model_reg.keys():
                dotted = f"{app}.{model}"
                await _ensure_content_type(app, model, dotted)
                seen.add(dotted)

            for entry in self.cards.iter_cards():
                virtual = self.cards.get_card_virtual(entry.key)
                dotted = virtual.dotted
                model_value = f"cards.{virtual.slug}"
                await _ensure_content_type(virtual.app_slug, model_value, dotted)
                seen.add(dotted)

            for virtual in self.registry.iter_virtual_views():
                dotted = virtual.dotted
                model_value = f"views.{virtual.slug}"
                await _ensure_content_type(virtual.app_slug, model_value, dotted)
                seen.add(dotted)

            existing = await self.adapter.fetch_all(
                self.adapter.all(self.AdminContentType)
            )
            for ct in existing:
                if ct.dotted in seen:
                    if not getattr(ct, "is_registered", True):
                        ct.is_registered = True
                        await self.adapter.save(ct)
                    continue
                dotted = ct.dotted or ""
                if ".cards." in dotted or ".views." in dotted:
                    await self.adapter.delete(ct)
                    continue
                if getattr(ct, "is_registered", True):
                    ct.is_registered = False
                    await self.adapter.save(ct)
        except Exception as exc:
            if self._migration_error_classifier.is_missing_schema(exc):
                system_config.flag_migrations_required()
                self.ct_map.clear()
                logger.error(
                    "Skipping admin content type synchronisation due to database error: %s. "
                    "Run your migrations before starting FreeAdmin.",
                    exc,
                )
                return
            raise

    def get_ct_id(self, app: str, model: str) -> int | None:
        """Return ct_id for (app, model) or ``None`` if not registered."""
        dotted = f"{app}.{model}"
        return self.ct_map.get(dotted)

    def get_ct_id_by_dotted(self, dotted: str) -> int | None:
        """Return content type id mapped by dotted name."""

        return self.ct_map.get(dotted)

    def parse_section_path(self, request: Request) -> tuple[bool, str | None, str | None]:
        """Extract section info from ``request.url.path``.

        The returned tuple consists of ``(is_settings, app_label, model_slug)``.
        ``is_settings`` is ``True`` when the path points to the settings section,
        otherwise ``False``. ``app_label`` and ``model_slug`` are extracted from
        ``/orm/<app>/<model>/`` or ``/settings/<app>/<model>/`` URLs. When the
        path does not include app/model parts they are returned as ``None``.
        """

        resolution = self.pages.resolve_request(request)
        return resolution.is_settings, resolution.app_label, resolution.model_slug

    @staticmethod
    def _format_app_label(app_label: str) -> str:
        display_label = app_label.replace("_", "\u00A0")
        if display_label:
            display_label = display_label[0].upper() + display_label[1:]
        return display_label

    def get_sidebar_apps(self, *, settings: bool) -> List[tuple[str, List[Dict[str, Any]]]]:
        """Return ORM registration entries grouped for sidebar rendering."""

        return SidebarBuilder.collect(
            admin_site=self,
            kind=SidebarBuilder.KIND_APPS,
            settings=settings,
        )

    
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
        return TemplateContextBuilder(self).build(
            request,
            user,
            page_title=page_title,
            app_label=app_label,
            model_name=model_name,
            is_settings=is_settings,
            extra=extra,
        )

    def get_sidebar_views(self, *, settings: bool) -> List[tuple[str, List[Dict[str, Any]]]]:
        """Return registered view entries grouped for sidebar rendering."""

        return self.pages.iter_sidebar_views(settings=settings)

    def _collect_card_assets(
        self,
        ctx: Dict[str, Any],
        *,
        prefix: str,
        static_segment: str,
    ) -> tuple[List[str], List[str]]:
        """Aggregate normalized asset URLs required by cards."""

        scripts: List[str] = []
        styles: List[str] = []
        seen_scripts: set[str] = set()
        seen_styles: set[str] = set()

        assets_payload = ctx.get("assets") if isinstance(ctx, dict) else None
        raw_script_sources: list[str] = []
        raw_style_sources: list[str] = []

        if isinstance(assets_payload, dict):
            raw_script_sources.extend(
                self._ensure_card_tuple(assets_payload.get("js"))
            )
            raw_style_sources.extend(
                self._ensure_card_tuple(assets_payload.get("css"))
            )

        raw_script_sources.extend(self._ensure_card_tuple(ctx.get("card_scripts")))
        raw_style_sources.extend(self._ensure_card_tuple(ctx.get("card_styles")))

        for raw_script in raw_script_sources:
            normalized = self._normalize_card_asset_path(str(raw_script), prefix, static_segment)
            if normalized and normalized not in seen_scripts:
                scripts.append(normalized)
                seen_scripts.add(normalized)

        for raw_style in raw_style_sources:
            normalized = self._normalize_card_asset_path(str(raw_style), prefix, static_segment)
            if normalized and normalized not in seen_styles:
                styles.append(normalized)
                seen_styles.add(normalized)

        cards_payload = ctx.get("cards") or ()
        if not isinstance(cards_payload, (list, tuple, set)):
            cards_payload = (cards_payload,)

        for payload in cards_payload:
            card_scripts, card_styles = self._resolve_card_assets(payload)
            for raw_script in card_scripts:
                normalized = self._normalize_card_asset_path(str(raw_script), prefix, static_segment)
                if normalized and normalized not in seen_scripts:
                    scripts.append(normalized)
                    seen_scripts.add(normalized)
            for raw_style in card_styles:
                normalized = self._normalize_card_asset_path(str(raw_style), prefix, static_segment)
                if normalized and normalized not in seen_styles:
                    styles.append(normalized)
                    seen_styles.add(normalized)

        return scripts, styles

    def _resolve_card_assets(self, payload: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return scripts and styles declared by a card payload."""

        if isinstance(payload, str):
            entry = self._get_card_entry_or_none(payload)
            if entry:
                return entry.scripts, entry.styles
            return (), ()

        if isinstance(payload, dict):
            scripts: list[str] = []
            styles: list[str] = []

            key = payload.get("key")
            if key is not None:
                entry = self._get_card_entry_or_none(str(key))
                if entry:
                    scripts.extend(entry.scripts)
                    styles.extend(entry.styles)

            scripts.extend(self._ensure_card_tuple(payload.get("scripts")))
            styles.extend(self._ensure_card_tuple(payload.get("styles")))

            assets_payload = payload.get("assets")
            if isinstance(assets_payload, dict):
                scripts.extend(self._ensure_card_tuple(assets_payload.get("js")))
                styles.extend(self._ensure_card_tuple(assets_payload.get("css")))

            return tuple(scripts), tuple(styles)

        scripts = self._ensure_card_tuple(getattr(payload, "scripts", None))
        styles = self._ensure_card_tuple(getattr(payload, "styles", None))
        if scripts or styles:
            return scripts, styles

        key = getattr(payload, "key", None)
        if key is not None:
            entry = self._get_card_entry_or_none(str(key))
            if entry:
                return entry.scripts, entry.styles
        return (), ()

    @staticmethod
    def _ensure_card_tuple(value: Any) -> tuple[str, ...]:
        """Coerce optional asset declarations into a tuple of strings."""

        if not value:
            return ()
        if isinstance(value, str):
            return (value,)
        try:
            return tuple(str(item) for item in value if item is not None)
        except TypeError:
            return (str(value),)

    def _normalize_card_asset_path(
        self, asset: str, prefix: str, static_segment: str
    ) -> str:
        """Return a safe asset URL derived from admin prefix and static segment."""

        normalized = asset.strip()
        if not normalized:
            return ""
        lowered = normalized.lower()
        if normalized.startswith(("http://", "https://", "//")) or lowered.startswith("data:"):
            return normalized
        if normalized.startswith("/"):
            return normalized

        base = prefix.rstrip("/")
        segment = static_segment.strip()
        if segment:
            segment = segment if segment.startswith("/") else f"/{segment}"
            base = f"{base}{segment}" if base else segment
        if base:
            base = base.rstrip("/")
        segment_token = segment.lstrip("/") if segment else ""
        path = normalized
        if segment_token and (
            path == segment_token or path.startswith(f"{segment_token}/")
        ):
            path = path[len(segment_token) :]
        path = path.lstrip("/")
        if base:
            return f"{base}/{path}" if path else base
        return f"/{path}" if path else "/"

    def _get_card_entry_or_none(self, key: str) -> CardEntry | None:
        """Return a registered card entry or ``None`` when missing."""

        try:
            return self.cards.get_card(key)
        except ValueError:
            logger.warning("Card '%s' referenced but not registered", key)
            return None

    def register_view(
        self,
        *,
        path: str,
        name: str,
        icon: str | None = None,
        label: str | None = None,
        settings: bool | None = None,
        include_in_sidebar: bool = True,
    ):
        """Register a simple view page handled by ``func``.

        Args:
            include_in_sidebar: When ``True`` the view is listed in the
                sidebar navigation grouping for its owning label.
        """

        return self.pages.register_view(
            path=path,
            name=name,
            icon=icon,
            label=label,
            settings=settings,
            include_in_sidebar=include_in_sidebar,
        )

    def register_settings(self, *, path: str, name: str, icon: str | None = None):
        """Register a settings page handled by ``func``."""
        return self.pages.register_settings(path=path, name=name, icon=icon)

    def register_public_view(
        self,
        *,
        path: str,
        name: str,
        template: str,
        icon: str | None = None,
    ):
        """Register a public-facing page handled by ``func``."""

        return self.pages.register_public_view(
            path=path,
            name=name,
            template=template,
            icon=icon,
        )

    def register_public_menu(
        self,
        *,
        title: str,
        path: str,
        icon: str | None = None,
    ) -> None:
        """Register a standalone public navigation item."""

        self.public_menu_builder.register_item(title=title, path=path, icon=icon)

    def register_user_menu(
        self, *, title: str, path: str, icon: str | None = None
    ) -> None:
        """Register a user menu item."""
        self.menu_builder.register_user_item(title=title, path=path, icon=icon)
        self.menu_builder.invalidate_main_menu()

    async def get_registered_cards(self, user: Any | None = None) -> List[Dict[str, Any]]:
        """Return registered cards filtered by the user's permissions."""

        user_key = self._resolve_card_cache_key(user)
        snapshot_token = ""
        snapshot_getter = getattr(self.permission_checker, "get_permission_snapshot", None)
        if callable(snapshot_getter):
            try:
                snapshot = snapshot_getter()
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to obtain permission snapshot for cards")
            else:
                if snapshot is not None:
                    snapshot_token = snapshot.isoformat()
        if self.card_cache is not None:
            await asyncio.to_thread(self.card_cache.prune_expired)
            if snapshot_token:
                cached = await asyncio.to_thread(self.card_cache.load, user_key)
                if cached is not None:
                    entries, _created_at, cached_snapshot = cached
                    if cached_snapshot == snapshot_token:
                        return entries

        cards: List[Dict[str, Any]] = []
        for entry in self.cards.iter_cards():
            if user is not None:
                try:
                    await self.permission_checker.check_card(
                        user,
                        entry.key,
                        PermAction.view,
                        admin_site=self,
                    )
                except (PermissionDenied, ValueError):
                    continue
            cards.append(
                {
                    "key": entry.key,
                    "app": entry.app,
                    "title": entry.title,
                    "template": entry.template,
                    "icon": entry.icon,
                    "channel": entry.channel,
                    "col_class": entry.col_class,
                    "scripts": list(entry.scripts),
                    "styles": list(entry.styles),
                    "dotted": entry.dotted,
                }
            )

        if self.card_cache is not None and snapshot_token:
            try:
                await asyncio.to_thread(
                    self.card_cache.store, user_key, cards, snapshot_token
                )
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to cache registered card list for user %s", user_key)
        return cards

    def get_user_menu(self) -> List[Dict[str, str | None]]:
        """Return user menu entries for the current site."""
        return [
            {"label": item.title, "url": item.path, "icon": item.icon}
            for item in self.menu_builder.build_user_menu(self.registry)
        ]

    # ==== Router ====
    def build_router(self, template_provider: TemplateProvider) -> APIRouter:
        router = APIRouter()
        templates = self.templates or template_provider.get_templates()
        setattr(router, "templates", templates)
        admin_prefix = system_config.get_cached(
            SettingsKey.ADMIN_PREFIX, self._settings.admin_path
        ).rstrip("/")

        def get_admin_api() -> dict[str, str]:
            """Expose fully-qualified API paths for templates."""

            api_prefix = system_config.get_cached(SettingsKey.API_PREFIX, "/api")
            schema_rel = system_config.get_cached(SettingsKey.API_SCHEMA, "/schema")
            list_filters_rel = system_config.get_cached(
                SettingsKey.API_LIST_FILTERS, "/list_filters"
            )
            base = admin_prefix

            return {
                "prefix": f"{base}{api_prefix}",
                "schema": f"{base}{api_prefix}{schema_rel}",
                "list_filters": f"{base}{api_prefix}{list_filters_rel}",
            }

        templates.env.globals.update(
            iter_settings_entries=self.registry.iter_settings,
            iter_orm_entries=self.registry.iter_orm,
            get_admin_api=get_admin_api,
            get_user_menu=self.get_user_menu,
        )

        orm_prefix = system_config.get_cached(SettingsKey.ORM_PREFIX, "/orm")
        settings_prefix = system_config.get_cached(SettingsKey.SETTINGS_PREFIX, "/settings")
        views_prefix = system_config.get_cached(SettingsKey.VIEWS_PREFIX, "/views")
        page_type_settings = system_config.get_cached(SettingsKey.PAGE_TYPE_SETTINGS)

        self._attach_auth_routes(router, templates)
        migrations_path = system_config.get_cached(
            SettingsKey.MIGRATIONS_PATH, "/migration-required"
        )

        @router.get(migrations_path, response_class=HTMLResponse)
        async def migrations_required(request: Request) -> HTMLResponse:
            ctx = self.build_template_ctx(
                request,
                None,
                page_title="Migrations required",
                extra={
                    "migration_message": "Run your migrations before starting FreeAdmin.",
                },
            )
            ctx["menu"] = []
            return templates.TemplateResponse(
                "pages/migrations_required.html", ctx, status_code=503
            )

        self._attach_page_routes(
            router,
            templates,
            orm_prefix,
            settings_prefix,
            views_prefix,
            page_type_settings,
            admin_prefix,
        )
        self._attach_api_routes(router)
        self._attach_crud_routes(router, orm_prefix, settings_prefix)

        return router

    def _attach_auth_routes(
        self, router: APIRouter, templates: Jinja2Templates
    ) -> None:
        logout_path = system_config.get_cached(SettingsKey.LOGOUT_PATH, "/logout")
        self.register_user_menu(title="Logout", path=logout_path)
        router.include_router(
            admin_auth_service.build_auth_router(templates), tags=["admin-auth"]
        )

    def _attach_page_routes(
        self,
        router: APIRouter,
        templates: Jinja2Templates,
        orm_prefix: str,
        settings_prefix: str,
        views_prefix: str,
        page_type_settings: str,
        admin_prefix: str,
    ) -> None:
        dashboard_perm_dep = self.permission_checker.require_view(
            PermAction.view,
            dotted=self._dashboard_virtual.dotted,
            admin_site=self,
        )

        @router.get("/", response_class=HTMLResponse)
        async def admin_index(
            request: Request,
            user: AdminUserDTO = Depends(
                admin_auth_service.require_permissions((), admin_site=self)
            ),
            _=Depends(dashboard_perm_dep),
        ) -> HTMLResponse:
            dash_title = await system_config.get(SettingsKey.DASHBOARD_PAGE_TITLE)
            orm_user = getattr(request.state, "user", None)
            card_entries = await self.get_registered_cards(user=orm_user)
            ctx = self.build_template_ctx(
                request,
                user,
                page_title=dash_title,
                extra={
                    "card_entries": card_entries,
                    "cards": card_entries,
                },
            )
            ctx["menu"] = self.menu_builder.build_main_menu(
                locale=self.get_locale(request)
            )
            return templates.TemplateResponse("pages/dashboard.html", ctx)

        self.pages.attach_admin_routes(
            router,
            templates=templates,
            page_type_settings=page_type_settings,
            views_prefix=views_prefix,
            settings_prefix=settings_prefix,
            orm_prefix=orm_prefix,
        )

    def _attach_api_routes(self, router: APIRouter) -> None:
        from freeadmin.contrib.apps.system.api.urls import (  # local import to avoid circular dependencies
            API_PREFIX,
            router as api_router,
        )

        router.include_router(api_router, prefix=API_PREFIX)
        router.include_router(card_router)

    def _attach_crud_routes(
        self, router: APIRouter, orm_prefix: str, settings_prefix: str
    ) -> None:
        templates = getattr(router, "templates", None)
        if templates is None:
            base_dir = Path(__file__).resolve().parents[2]
            templates = Jinja2Templates(directory=str(base_dir / "templates"))
        for entry in self.registry.iter_orm():
            app_label = entry.app
            model_slug = entry.model
            prefix = f"{orm_prefix}/{app_label}/{model_slug}"
            CrudRouterBuilder.mount(
                router,
                admin_site=self,
                prefix=prefix,
                admin_cls=entry.admin_cls,
                perms="model",
                app_label=app_label,
            )
            admin = self.model_reg.get((app_label.lower(), model_slug.lower()))
            if admin is None:
                continue
            export_endpoint_name = f"{app_label}_{model_slug}_export_wizard"
            export_preview_endpoint_name = f"{app_label}_{model_slug}_export_preview"
            export_run_endpoint_name = f"{app_label}_{model_slug}_export_run"
            export_done_endpoint_name = f"{app_label}_{model_slug}_export_done"
            admin.export_endpoint_name = export_endpoint_name
            admin.export_preview_endpoint_name = export_preview_endpoint_name
            admin.export_run_endpoint_name = export_run_endpoint_name
            admin.export_done_endpoint_name = export_done_endpoint_name
            export_service = ExportService(self.adapter)
            scope_query_service = ScopeQueryService(self.adapter)
            scope_token_service = ScopeTokenService()
            scope_token_service = ScopeTokenService()
            if admin.perm_export:
                perm_export = self.permission_checker.require_model(
                    admin.perm_export,
                    app_value=app_label,
                    model_value=model_slug,
                    admin_site=self,
                )
            else:
                async def perm_export(request: Request) -> None:
                    return None
            if admin.perm_import:
                perm_import = self.permission_checker.require_model(
                    admin.perm_import,
                    app_value=app_label,
                    model_value=model_slug,
                    admin_site=self,
                )
            else:
                async def perm_import(request: Request) -> None:
                    return None

            @router.api_route(
                prefix + "/export/",
                methods=["GET", "POST"],
                response_class=HTMLResponse,
                name=export_endpoint_name,
            )
            async def export_step1(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                app_label: str = app_label,
                model_slug: str = model_slug,
            ) -> HTMLResponse:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                ctx = self.build_template_ctx(
                    request,
                    user,
                    page_title="Export",
                    app_label=app_label,
                    model_name=model_slug,
                )
                ctx["fields"] = list(admin.get_export_fields())
                return templates.TemplateResponse(
                    "context/export.html", ctx
                )

            @router.post(prefix + "/export/preview", name=export_preview_endpoint_name)
            async def export_preview(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                export_service: ExportService = Depends(lambda: export_service),
                scope_query_service: ScopeQueryService = Depends(
                    lambda: scope_query_service
                ),
            ) -> Dict[str, Any]:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                payload = await request.json()
                allowed = list(admin.get_export_fields())
                fields = [f for f in payload.get("fields", allowed) if f in allowed]
                md = self.adapter.get_model_descriptor(admin.model)
                scope = payload.get("scope")
                if scope is None:
                    token = payload.get("scope_token")
                    if token is None:
                        raise HTTPException(status_code=400, detail="Missing scope")
                    try:
                        scope = scope_token_service.verify(token)
                    except ValueError:
                        raise HTTPException(status_code=400, detail="Invalid scope_token")
                qs = scope_query_service.build_queryset(
                    admin, md, request, user, scope
                )
                rows = await export_service.preview(qs, fields)
                return {"count": len(rows), "rows": rows}

            @router.post(prefix + "/export/run", name=export_run_endpoint_name)
            async def export_run(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                export_service: ExportService = Depends(lambda: export_service),
                scope_query_service: ScopeQueryService = Depends(
                    lambda: scope_query_service
                ),
            ) -> Dict[str, Any]:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                payload = await request.json()
                allowed = list(admin.get_export_fields())
                fields = [f for f in payload.get("fields", allowed) if f in allowed]
                fmt = payload.get("fmt", "json")
                md = self.adapter.get_model_descriptor(admin.model)
                scope = payload.get("scope")
                if scope is None:
                    token = payload.get("scope_token")
                    if token is None:
                        raise HTTPException(status_code=400, detail="Missing scope")
                    try:
                        scope = scope_token_service.verify(token)
                    except ValueError:
                        raise HTTPException(status_code=400, detail="Invalid scope_token")
                qs = scope_query_service.build_queryset(
                    admin, md, request, user, scope
                )
                token = await export_service.run(
                    qs, fields, fmt, model_name=admin.model.__name__
                )
                return {"token": token}

            @router.get(prefix + "/export/done/{token}", name=export_done_endpoint_name)
            async def export_done(
                token: str,
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                export_service: ExportService = Depends(lambda: export_service),
            ) -> StreamingResponse:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                cached = export_service.get_file(token)
                def iterfile() -> Any:
                    with cached.path.open("rb") as f:
                        yield from f
                response = StreamingResponse(iterfile(), media_type=cached.mime)
                response.headers[
                    "Content-Disposition"
                ] = f"attachment; filename={cached.filename}"
                response.headers["Content-Type"] = cached.mime
                return response

            import_endpoint_name = f"{app_label}_{model_slug}_import_wizard"
            import_preview_name = f"{app_label}_{model_slug}_import_preview"
            import_run_name = f"{app_label}_{model_slug}_import_run"
            admin.import_endpoint_name = import_endpoint_name
            admin.import_preview_endpoint_name = import_preview_name
            admin.import_run_endpoint_name = import_run_name

            @router.api_route(
                prefix + "/import/",
                methods=["GET", "POST"],
                response_class=HTMLResponse,
                name=import_endpoint_name,
            )
            async def import_step1(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_import),
                admin=admin,
                app_label: str = app_label,
                model_slug: str = model_slug,
            ) -> HTMLResponse:
                request.state.user_dto = user
                if not admin.has_import_perm(request):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Import not permitted",
                    )
                ctx = self.build_template_ctx(
                    request,
                    user,
                    page_title="Import",
                    app_label=app_label,
                    model_name=model_slug,
                )
                ctx.update(
                    fields=list(admin.get_import_fields()),
                    required=set(admin.get_required_import_fields()),
                )
                return templates.TemplateResponse(
                    "context/import.html", ctx
                )

            @router.post(prefix + "/import/preview", name=import_preview_name)
            async def import_preview(
                request: Request,
                file: UploadFile = File(...),
                fields: list[str] = Form(...),
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_import),
                admin=admin,
                import_service: ImportService = Depends(
                    lambda: self._import_service
                ),
            ) -> Dict[str, Any]:
                request.state.user_dto = user
                if not admin.has_import_perm(request):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Import not permitted",
                    )
                token = await import_service.cache_upload(file)
                rows = await import_service.preview(token, fields)
                return {"token": token, "rows": rows}

            @router.post(prefix + "/import/run", name=import_run_name)
            async def import_run(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_import),
                admin=admin,
                import_service: ImportService = Depends(
                    lambda: self._import_service
                ),
            ) -> Dict[str, Any]:
                request.state.user_dto = user
                if not admin.has_import_perm(request):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Import not permitted",
                    )
                payload = await request.json()
                token = payload.get("token")
                dry = payload.get("dry", False)
                fields = payload.get("fields") or list(admin.get_import_fields())
                report = await import_service.run(admin, token, fields, dry=dry)
                await import_service.cleanup(token)
                return report.__dict__

        for entry in self.registry.iter_settings():
            app_label = entry.app
            model_slug = entry.model
            prefix = f"{settings_prefix}/{app_label}/{model_slug}"
            CrudRouterBuilder.mount(
                router,
                admin_site=self,
                prefix=prefix,
                admin_cls=entry.admin_cls,
                perms="global",
                app_label=app_label,
            )
            admin = self.model_reg.get((app_label.lower(), model_slug.lower()))
            if admin is None:
                continue
            export_endpoint_name = f"{app_label}_{model_slug}_export_wizard"
            export_preview_endpoint_name = f"{app_label}_{model_slug}_export_preview"
            export_run_endpoint_name = f"{app_label}_{model_slug}_export_run"
            export_done_endpoint_name = f"{app_label}_{model_slug}_export_done"
            admin.export_endpoint_name = export_endpoint_name
            admin.export_preview_endpoint_name = export_preview_endpoint_name
            admin.export_run_endpoint_name = export_run_endpoint_name
            admin.export_done_endpoint_name = export_done_endpoint_name
            export_service = ExportService(self.adapter)
            scope_query_service = ScopeQueryService(self.adapter)
            if admin.perm_export:
                perm_export = self.permission_checker.require_view(
                    admin.perm_export, admin_site=self
                )
            else:
                async def perm_export(request: Request) -> None:
                    return None

            @router.api_route(
                prefix + "/export/",
                methods=["GET", "POST"],
                response_class=HTMLResponse,
                name=export_endpoint_name,
            )
            async def export_step1(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                app_label: str = app_label,
                model_slug: str = model_slug,
            ) -> HTMLResponse:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                ctx = self.build_template_ctx(
                    request,
                    user,
                    page_title="Export",
                    app_label=app_label,
                    model_name=model_slug,
                )
                ctx["fields"] = list(admin.get_export_fields())
                return templates.TemplateResponse(
                    "context/export.html", ctx
                )

            @router.post(prefix + "/export/preview", name=export_preview_endpoint_name)
            async def export_preview(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                export_service: ExportService = Depends(lambda: export_service),
                scope_query_service: ScopeQueryService = Depends(
                    lambda: scope_query_service
                ),
            ) -> Dict[str, Any]:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                payload = await request.json()
                allowed = list(admin.get_export_fields())
                fields = [f for f in payload.get("fields", allowed) if f in allowed]
                md = self.adapter.get_model_descriptor(admin.model)
                scope = payload.get("scope")
                if scope is None:
                    token = payload.get("scope_token")
                    if token is None:
                        raise HTTPException(status_code=400, detail="Missing scope")
                    try:
                        scope = scope_token_service.verify(token)
                    except ValueError:
                        raise HTTPException(status_code=400, detail="Invalid scope_token")
                qs = scope_query_service.build_queryset(
                    admin, md, request, user, scope
                )
                rows = await export_service.preview(qs, fields)
                return {"count": len(rows), "rows": rows}

            @router.post(prefix + "/export/run", name=export_run_endpoint_name)
            async def export_run(
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                export_service: ExportService = Depends(lambda: export_service),
                scope_query_service: ScopeQueryService = Depends(
                    lambda: scope_query_service
                ),
            ) -> Dict[str, Any]:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                payload = await request.json()
                allowed = list(admin.get_export_fields())
                fields = [f for f in payload.get("fields", allowed) if f in allowed]
                fmt = payload.get("fmt", "json")
                md = self.adapter.get_model_descriptor(admin.model)
                scope = payload.get("scope")
                if scope is None:
                    token = payload.get("scope_token")
                    if token is None:
                        raise HTTPException(status_code=400, detail="Missing scope")
                    try:
                        scope = scope_token_service.verify(token)
                    except ValueError:
                        raise HTTPException(status_code=400, detail="Invalid scope_token")
                qs = scope_query_service.build_queryset(
                    admin, md, request, user, scope
                )
                token = await export_service.run(
                    qs, fields, fmt, model_name=admin.model.__name__
                )
                return {"token": token}

            @router.get(prefix + "/export/done/{token}", name=export_done_endpoint_name)
            async def export_done(
                token: str,
                request: Request,
                user: AdminUserDTO = Depends(
                    admin_auth_service.get_current_admin_user
                ),
                _=Depends(perm_export),
                admin=admin,
                export_service: ExportService = Depends(lambda: export_service),
            ) -> StreamingResponse:
                request.state.user_dto = user
                if not (user.is_superuser or admin.has_export_perm(request)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Export not permitted",
                    )
                cached = export_service.get_file(token)

                def iterfile() -> Any:
                    with cached.path.open("rb") as f:
                        yield from f

                response = StreamingResponse(iterfile(), media_type=cached.mime)
                response.headers[
                    "Content-Disposition"
                ] = f"attachment; filename={cached.filename}"
                response.headers["Content-Type"] = cached.mime
                return response

        self.menu_builder.build_main_menu(locale=self.get_locale())

# The End

