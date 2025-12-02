# -*- coding: utf-8 -*-
"""
keys

Available settings keys for the system.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

# settings_keys.py
from .choices import StrChoices  # adjust import path as needed


class SettingsKey(StrChoices):
    """Available settings keys for the system."""

    # --- Titles / Pages ---
    DEFAULT_ADMIN_TITLE   = ("DEFAULT_ADMIN_TITLE", "Admin panel title")
    DASHBOARD_PAGE_TITLE  = ("DASHBOARD_PAGE_TITLE", "Dashboard page title")
    VIEWS_PAGE_TITLE      = ("VIEWS_PAGE_TITLE", "Views section title")
    ORM_PAGE_TITLE        = ("ORM_PAGE_TITLE", "ORM section title")
    SETTINGS_PAGE_TITLE   = ("SETTINGS_PAGE_TITLE", "Settings section title")

    # --- Page icons ---
    VIEWS_PAGE_ICON       = ("VIEWS_PAGE_ICON", "Views icon (Bootstrap 5 class)")
    ORM_PAGE_ICON         = ("ORM_PAGE_ICON", "ORM icon (Bootstrap 5 class)")
    SETTINGS_PAGE_ICON    = ("SETTINGS_PAGE_ICON", "Settings icon (Bootstrap 5 class)")

    # --- Security ---
    PASSWORD_ALGO         = ("PASSWORD_ALGO", "Password hashing algorithm")
    PASSWORD_ITERATIONS   = ("PASSWORD_ITERATIONS", "Password hashing iterations")

    # --- Page types (settings keys for canonical slug values) ---
    PAGE_TYPE_ORM         = ("PAGE_TYPE_ORM", "Page type: ORM")
    PAGE_TYPE_VIEW        = ("PAGE_TYPE_VIEW", "Page type: View")
    PAGE_TYPE_SETTINGS    = ("PAGE_TYPE_SETTINGS", "Page type: Settings")

    # --- Pagination ---
    DEFAULT_PER_PAGE      = ("DEFAULT_PER_PAGE", "Default page size")
    MAX_PER_PAGE          = ("MAX_PER_PAGE", "Max page size")

    # --- API endpoints ---
    API_PREFIX            = ("API_PREFIX", "API prefix")
    API_SCHEMA            = ("API_SCHEMA", "Schema endpoint")
    API_LIST_FILTERS      = ("API_LIST_FILTERS", "List filters endpoint")

    # --- Auth / Session ---
    LOGIN_PATH            = ("LOGIN_PATH", "Login path")
    LOGOUT_PATH           = ("LOGOUT_PATH", "Logout path")
    SETUP_PATH            = ("SETUP_PATH", "Setup path")
    SESSION_KEY           = ("SESSION_KEY", "Admin session cookie key")

    # --- Section prefixes ---
    ORM_PREFIX            = ("ORM_PREFIX", "ORM section prefix")
    SETTINGS_PREFIX       = ("SETTINGS_PREFIX", "Settings section prefix")
    VIEWS_PREFIX          = ("VIEWS_PREFIX", "Views section prefix")

    # --- Static ---
    STATIC_PATH           = ("STATIC_PATH", "Static files path")
    STATIC_URL_SEGMENT    = ("STATIC_URL_SEGMENT", "Static URL segment")
    STATIC_ROUTE_NAME     = ("STATIC_ROUTE_NAME", "Static route name")

# The End
