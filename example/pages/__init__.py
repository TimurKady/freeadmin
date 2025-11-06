# -*- coding: utf-8 -*-
"""
pages

Example view registrations for the FreeAdmin demo project.

Version:0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations

from .home import ExampleWelcomePage, example_welcome_page
from .public_welcome import PublicWelcomePage, public_welcome_page

__all__ = [
    "ExampleWelcomePage",
    "example_welcome_page",
    "PublicWelcomePage",
    "public_welcome_page",
]

# The End

