# -*- coding: utf-8 -*-
"""
main

Example application bootstrap for FreeAdmin.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from freeadmin.application import ApplicationFactory
from freeadmin.core.boot import BootManager

from .orm import ExampleORMConfig
from .routers import ExampleAdminRouters
from .settings import ExampleSettings


class ExampleApplication(ApplicationFactory):
    """Assemble a runnable FreeAdmin demonstration project."""

    settings_class = ExampleSettings
    orm_config_class = ExampleORMConfig
    router_manager_class = ExampleAdminRouters
    default_packages = ("example.apps", "example.pages")

    def __init__(self) -> None:
        """Initialise the factory with example defaults."""

        super().__init__(
            settings=self.settings_class(),
            orm_config=self.orm_config_class,
            router_manager=self.router_manager_class(),
            packages=self.default_packages,
        )

    @property
    def boot_manager(self) -> BootManager:
        """Return the BootManager coordinating FreeAdmin bootstrapping."""

        return self._boot


__all__ = ["ExampleApplication"]

# The End

