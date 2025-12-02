# -*- coding: utf-8 -*-
"""
passwords

Password generation utility.

Version: 0.1.0
Author: Timur Kady
Email: timurkady@yandex.com
"""

from __future__ import annotations
import base64
import os
import hashlib
import hmac
from typing import Tuple

from ..core.settings import SettingsKey, system_config


def _pbkdf2_sha256(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


async def make_password(password: str, *, iterations: int | None = None) -> str:
    if iterations is None:
        iterations = await system_config.get(SettingsKey.PASSWORD_ITERATIONS)
    salt = os.urandom(16)
    algo = await system_config.get(SettingsKey.PASSWORD_ALGO)
    dk = _pbkdf2_sha256(password, salt, iterations)
    return f"{algo}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def _parse(stored: str) -> Tuple[str, int, bytes, bytes]:
    algo, iters_s, salt_b64, hash_b64 = stored.split("$", 3)
    return algo, int(iters_s), base64.b64decode(salt_b64), base64.b64decode(hash_b64)


async def check_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, dh = _parse(stored)
        expected_algo = await system_config.get(SettingsKey.PASSWORD_ALGO)
        if algo != expected_algo:
            return False
        cand = _pbkdf2_sha256(password, salt, iterations)
        return hmac.compare_digest(cand, dh)
    except Exception:
        return False

# The End
