# -*- coding: utf-8 -*-
"""
project_initializer

Project scaffolding helpers for the init CLI command.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from .reporting import CreationReport


ROUTER_TEMPLATE_CLASS_NAME = "ProjectRouterAggregator"


class PackageInitializer:
    """Create ``__init__`` markers for project package directories."""

    def __init__(self, package_directories: Iterable[str]) -> None:
        """Remember target directories requiring package initialization."""

        self._package_directories = tuple(package_directories)

    def ensure_packages(self, project_root: Path, report: CreationReport) -> None:
        """Create empty ``__init__.py`` files for configured directories."""

        for directory in self._package_directories:
            package_path = project_root / directory / "__init__.py"
            if package_path.exists():
                report.add_skipped(package_path)
                continue
            package_path.write_text("", encoding="utf-8")
            report.add_created(package_path)


class ConfigTemplateProvider:
    """Generate configuration file templates for project scaffolding."""

    def __init__(self, project_name: str) -> None:
        """Remember the target project name for template rendering."""
        self._project_name = project_name

    def templates(self) -> Dict[str, str]:
        """Return all available configuration templates keyed by filename."""
        return {
            "main.py": self._main_template().format(project_name=self._project_name),
            "orm.py": self._orm_template().format(project_name=self._project_name),
            "settings.py": self._settings_template().format(project_name=self._project_name),
            "routers.py": self._routers_template().format(
                project_name=self._project_name,
                router_class=ROUTER_TEMPLATE_CLASS_NAME,
            ),
        }

    def _main_template(self) -> str:
        return '''# -*- coding: utf-8 -*-
"""
Application bootstrap for {project_name}.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import List

from fastapi import FastAPI

from freeadmin.core.boot import BootManager
from freeadmin.core.orm import ORMConfig

from .orm import ORM
from .settings import ProjectSettings


class ApplicationFactory:
    """Create FastAPI applications for the project."""

    def __init__(
        self,
        *,
        settings: ProjectSettings | None = None,
        orm: ORMConfig | None = None,
        packages: Iterable[str] | None = None,
    ) -> None:
        """Configure dependencies required to build the application."""

        self._settings = settings or ProjectSettings()
        self._orm = orm or ORM
        self._orm_lifecycle = self._orm.create_lifecycle()
        self._boot = BootManager(adapter_name=self._orm_lifecycle.adapter_name)
        self._app = FastAPI(title=self._settings.project_title)
        self._packages: List[str] = list(packages or ["apps", "pages"])
        self._orm_events_bound = False

    def build(self) -> FastAPI:
        """Return a FastAPI instance wired with FreeAdmin integration."""

        self._bind_orm_events()
        self._boot.init(
            self._app,
            adapter=self._orm_lifecycle.adapter_name,
            packages=self._packages,
        )
        return self._app

    def _bind_orm_events(self) -> None:
        """Attach ORM lifecycle hooks to the FastAPI application."""

        if self._orm_events_bound:
            return
        self._orm_lifecycle.bind(self._app)
        self._orm_events_bound = True


app = ApplicationFactory().build()


# The End

'''

    def _orm_template(self) -> str:
        return '''# -*- coding: utf-8 -*-
"""
Database configuration entry point for {project_name}.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from freeadmin.contrib.adapters.tortoise.adapter import (
    Adapter as TortoiseAdapter,
)
from freeadmin.core.orm import ORMConfig

# Adjust the adapter name to match the backend registered with FreeAdmin.
DB_ADAPTER = "tortoise"
"""Name of the FreeAdmin adapter powering the ORM layer."""

# List your project model modules so migrations discover application models.
APPLICATION_MODEL_MODULES: tuple[str, ...] = (
    "apps.example.models",
)
"""Application model modules included in the project."""

# Keep the adapter-provided modules so FreeAdmin can bootstrap built-in functionality.
# Include adapter-provided admin models to enable the FreeAdmin UI resources and add
# Aerich's migration tables so `aerich` commands initialise correctly.
ADMIN_MODEL_MODULES: tuple[str, ...] = tuple(
    [*TortoiseAdapter.model_modules, "aerich.models"]
)
"""Admin model modules shipped with the selected adapter and Aerich."""

# Update the connections and app configuration to reflect your data sources.
ORM_CONFIG: Dict[str, Dict[str, Any]] = {{
    "connections": {{
        "default": "sqlite://:memory:",
    }},
    "apps": {{
        "admin": {{
            "models": list(ADMIN_MODEL_MODULES),
            "default_connection": "default",
        }},
        "models": {{
            "models": list(APPLICATION_MODEL_MODULES),
            "default_connection": "default",
        }},
    }},
}}
"""Declarative configuration mapping describing the ORM setup."""

# Build a reusable ORMConfig instance and import it from config.main when wiring FastAPI.
ORM: ORMConfig = ORMConfig.build(
    adapter_name=DB_ADAPTER,
    config=deepcopy(ORM_CONFIG),
)
"""Ready-to-use ORMConfig instance exported for the application factory."""


__all__ = [
    "ADMIN_MODEL_MODULES",
    "APPLICATION_MODEL_MODULES",
    "DB_ADAPTER",
    "ORM",
    "ORM_CONFIG",
]


# The End

'''

    def _settings_template(self) -> str:
        return '''# -*- coding: utf-8 -*-
"""
Primary configuration object for {project_name}.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class ProjectSettings(BaseSettings):
    """Basic settings model for the generated project."""

    debug: bool = True
    database_url: str = "sqlite:///db.sqlite3"
    project_title: str = "{project_name} administration"


settings = ProjectSettings()


# The End

'''

    def _routers_template(self) -> str:
        return '''# -*- coding: utf-8 -*-
"""
routers

Routing helpers for {project_name}.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from freeadmin.core.interface.site import AdminSite
from freeadmin.core.runtime.hub import admin_site
from freeadmin.core.network.router import RouterAggregator


class {router_class}(RouterAggregator):
    """Aggregate routers exposed by {project_name}."""

    def __init__(
        self,
        site: AdminSite,
        *,
        prefix: str | None = None,
        additional_routers: tuple[tuple[APIRouter, str | None], ...] | None = None,
    ) -> None:
        """Initialise the aggregator with the admin site and prefix."""

        super().__init__(
            site=site,
            prefix=prefix,
            additional_routers=additional_routers,
        )
        # Declare routers here when you do not want to pass them in as
        # ``additional_routers``.
        # self.add_additional_router(reports_router, "/reports")

    def mount(self, app: FastAPI, prefix: str | None = None) -> None:  # type: ignore[override]
        """Mount the admin UI and project routers onto ``app``."""

        super().mount(app, prefix=prefix)
        # Delegate admin mounting to ``RouterAggregator`` and extend this
        # method only when additional side effects are required.


ROUTERS: {router_class} = {router_class}(site=admin_site)


__all__ = ["{router_class}", "ROUTERS"]


# The End

'''


class ProjectInitializer:
    """Build the base filesystem layout for a Freeadmin project."""

    _DIRECTORIES = (
        "config",
        "apps",
        "pages",
        "static",
        "templates",
    )

    _PACKAGE_DIRECTORIES = (
        "config",
        "apps",
    )

    _README_TEMPLATE = """# {project_name}\n\nThis project was generated by the freeadmin CLI utility. Customize the configuration in the `config/` directory.\n"""

    def __init__(self, base_path: Path | None = None) -> None:
        """Prepare the initializer with the filesystem base path."""
        self._base_path = base_path or Path.cwd()
        self._package_initializer = PackageInitializer(self._PACKAGE_DIRECTORIES)

    def create_project(self, project_name: str) -> CreationReport:
        """Create or update the project skeleton under the base path."""
        project_root = self._base_path / project_name
        report = CreationReport(project_root)

        if project_root.exists():
            report.add_skipped(project_root)
        else:
            project_root.mkdir(parents=True, exist_ok=True)
            report.add_created(project_root)

        for directory in self._DIRECTORIES:
            directory_path = project_root / directory
            if directory_path.exists():
                report.add_skipped(directory_path)
                continue
            directory_path.mkdir(parents=True, exist_ok=True)
            report.add_created(directory_path)

        self._package_initializer.ensure_packages(project_root, report)
        self._create_config_files(project_root, report, project_name)
        self._create_readme(project_root, report, project_name)
        return report

    def _create_config_files(
        self,
        project_root: Path,
        report: CreationReport,
        project_name: str,
    ) -> None:
        config_dir = project_root / "config"
        templates = ConfigTemplateProvider(project_name).templates()
        for file_name, template in templates.items():
            file_path = config_dir / file_name
            if file_path.exists():
                report.add_skipped(file_path)
                continue
            file_path.write_text(
                template,
                encoding="utf-8",
            )
            report.add_created(file_path)

    def _create_readme(
        self,
        project_root: Path,
        report: CreationReport,
        project_name: str,
    ) -> None:
        readme_path = project_root / "README.md"
        if readme_path.exists():
            report.add_skipped(readme_path)
            return
        readme_path.write_text(
            self._README_TEMPLATE.format(project_name=project_name),
            encoding="utf-8",
        )
        report.add_created(readme_path)


# The End

