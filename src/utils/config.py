#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — Configuration Utilities

Load configuration from environment variables and config files.
"""

import os
import json
from pathlib import Path


def load_env(env_file: str | Path | None = None) -> dict[str, str]:
    """Load environment variables from .env file.

    Args:
        env_file: Path to .env file. Defaults to .env in current directory.

    Returns:
        Dict of loaded key-value pairs.
    """
    if env_file is None:
        env_file = Path(".env")
    else:
        env_file = Path(env_file)

    loaded = {}
    if not env_file.exists():
        return loaded

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
                loaded[key] = value

    return loaded


def get_api_config(
    api_key_env: str = "MIMO_API_KEY",
    base_url_env: str = "MIMO_BASE_URL",
    default_url: str = "https://token-plan-sgp.xiaomimimo.com/v1",
) -> tuple[str, str]:
    """Get API configuration from environment variables.

    Args:
        api_key_env: Environment variable name for API key.
        base_url_env: Environment variable name for base URL.
        default_url: Default base URL if env var not set.

    Returns:
        Tuple of (api_key, base_url).

    Raises:
        EnvironmentError: If API key is not set.
    """
    load_env()  # Auto-load .env if present

    api_key = os.environ.get(api_key_env, "")
    base_url = os.environ.get(base_url_env, default_url)

    if not api_key:
        raise EnvironmentError(
            f"{api_key_env} environment variable is required.\n"
            f"Set it with: export {api_key_env}=your_key_here\n"
            f"Or create a .env file with: {api_key_env}=your_key_here"
        )

    return api_key, base_url


def load_json_config(config_path: str | Path) -> dict:
    """Load a JSON configuration file.

    Args:
        config_path: Path to JSON file.

    Returns:
        Parsed configuration dict.

    Raises:
        FileNotFoundError: If config file doesn't exist.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
