# -*- coding: utf-8 -*-
"""
defaults

Default settings mapping.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from .keys import SettingsKey

DEFAULT_SETTINGS: dict[SettingsKey, tuple[object, str]] = {
    # Titles / Pages
    SettingsKey.DEFAULT_ADMIN_TITLE:   ("Admin", "string"),
    SettingsKey.DASHBOARD_PAGE_TITLE:  ("Dashboard", "string"),
    SettingsKey.VIEWS_PAGE_TITLE:      ("Views", "string"),
    SettingsKey.ORM_PAGE_TITLE:        ("ORM", "string"),
    SettingsKey.SETTINGS_PAGE_TITLE:   ("Settings", "string"),

    # Page icons
    SettingsKey.VIEWS_PAGE_ICON:       ("bi-eye", "string"),
    SettingsKey.ORM_PAGE_ICON:         ("bi-diagram-3", "string"),
    SettingsKey.SETTINGS_PAGE_ICON:    ("bi-gear", "string"),

    # Security
    SettingsKey.PASSWORD_ALGO:         ("pbkdf2_sha256", "string"),
    SettingsKey.PASSWORD_ITERATIONS:   (390000, "int"),

    # Page types
    SettingsKey.PAGE_TYPE_ORM:         ("orm", "string"),
    SettingsKey.PAGE_TYPE_VIEW:        ("view", "string"),
    SettingsKey.PAGE_TYPE_SETTINGS:    ("settings", "string"),

    # Pagination
    SettingsKey.DEFAULT_PER_PAGE:      (20, "int"),
    SettingsKey.MAX_PER_PAGE:          (100, "int"),

    # API endpoints
    SettingsKey.API_PREFIX:            ("/api", "string"),
    SettingsKey.API_SCHEMA:            ("/api/schema", "string"),
    SettingsKey.API_LIST_FILTERS:      ("/api/list_filters", "string"),

    # Auth / Session
    SettingsKey.LOGIN_PATH:            ("/login", "string"),
    SettingsKey.LOGOUT_PATH:           ("/logout", "string"),
    SettingsKey.SETUP_PATH:            ("/setup", "string"),
    SettingsKey.SESSION_KEY:           ("admin_user_id", "string"),

    # Section prefixes
    SettingsKey.ORM_PREFIX:            ("/orm", "string"),
    SettingsKey.SETTINGS_PREFIX:       ("/settings", "string"),
    SettingsKey.VIEWS_PREFIX:          ("/views", "string"),

    # Static
    SettingsKey.STATIC_PATH:           ("/static", "string"),
    SettingsKey.STATIC_URL_SEGMENT:    ("/static", "string"),
    SettingsKey.STATIC_ROUTE_NAME:     ("admin-static", "string"),
}

# The End
