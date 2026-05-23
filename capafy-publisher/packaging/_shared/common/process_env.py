from __future__ import annotations

import os
import platform
import re
import shlex
import subprocess
from pathlib import Path
from typing import Mapping

from packaging._shared.common.home import current_home_from_env, safe_expanduser_path


_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SHELL_ENV_FILES = (
    ".zshenv",
    ".zprofile",
    ".zshrc",
    ".bash_profile",
    ".bash_login",
    ".bashrc",
    ".profile",
)
_WINDOWS_ENV_KEYS = (
    ("HKEY_CURRENT_USER", r"Environment"),
    ("HKEY_LOCAL_MACHINE", r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
)
_URL_PROXY_OS_FALLBACK_NAMES_BY_TARGET = {
    "claude_code": frozenset({
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
    }),
    "codex": frozenset({
        "CODEX_API_KEY",
        "CODEX_ACCESS_TOKEN",
        "OPENAI_BASE_URL",
    }),
    "openclaw": frozenset({
        "OPENCLAW_LIVE_OPENAI_KEY",
        "OPENAI_API_KEYS",
        "OPENAI_API_KEY",
        "OPENCLAW_LIVE_ANTHROPIC_KEY",
        "OPENCLAW_LIVE_ANTHROPIC_KEYS",
        "ANTHROPIC_API_KEYS",
        "ANTHROPIC_API_KEY",
        "OPENCLAW_LIVE_GEMINI_KEY",
        "GEMINI_API_KEYS",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    }),
}


def collect_publish_process_env(
    *,
    environ: Mapping[str, str] | None = None,
    user_home: Path | None = None,
    names: set[str] | frozenset[str] | None = None,
    os_fallback_names: set[str] | frozenset[str] | None = None,
    platform_system: str | None = None,
) -> dict[str, str]:
    wanted = _normalize_names(names)
    env = _filter_env(environ if environ is not None else os.environ, wanted)

    fallback_names = _normalize_names(os_fallback_names)
    if fallback_names is None and wanted is not None:
        fallback_names = wanted
    if not fallback_names:
        return env

    home = _resolve_home(user_home, env)
    system_name = platform_system or platform.system()
    for name, value in _collect_platform_env(system_name, home, fallback_names).items():
        env.setdefault(name, value)
    return env


def url_proxy_os_fallback_names(env_id: str | None) -> frozenset[str]:
    target_id = str(env_id or "").strip()
    if target_id in _URL_PROXY_OS_FALLBACK_NAMES_BY_TARGET:
        return _URL_PROXY_OS_FALLBACK_NAMES_BY_TARGET[target_id]
    names: set[str] = set()
    for target_names in _URL_PROXY_OS_FALLBACK_NAMES_BY_TARGET.values():
        names.update(target_names)
    return frozenset(names)


def _normalize_names(names: set[str] | frozenset[str] | None) -> set[str] | None:
    if names is None:
        return None
    return {name for name in (str(item).strip() for item in names) if _ENV_NAME_PATTERN.fullmatch(name)}


def _wanted(name: str, names: set[str] | None) -> bool:
    return bool(name and _ENV_NAME_PATTERN.fullmatch(name) and (names is None or name in names))


def _filter_env(environ: Mapping[str, str], names: set[str] | None) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in environ.items():
        name = str(key).strip()
        if not _wanted(name, names) or not isinstance(value, str):
            continue
        env[name] = value
    return env


def _resolve_home(user_home: Path | None, env: Mapping[str, str]) -> Path | None:
    if user_home is not None:
        return safe_expanduser_path(user_home, environ=env)
    return current_home_from_env(env)


def _collect_platform_env(system_name: str, home: Path | None, names: set[str] | None) -> dict[str, str]:
    normalized = str(system_name or "").strip()
    if normalized == "Windows":
        return _collect_windows_env(names)
    if normalized == "Darwin":
        env = _collect_macos_launchctl_env(names)
        _fill_missing(env, _collect_posix_shell_env(home, names), names)
        return env
    if normalized == "Linux":
        env = _collect_posix_shell_env(home, names)
        _fill_missing(env, _collect_etc_environment(names), names)
        return env
    return _collect_posix_shell_env(home, names)


def _fill_missing(target: dict[str, str], source: Mapping[str, str], names: set[str] | None) -> None:
    for name, value in source.items():
        if _wanted(name, names) and name not in target:
            target[name] = value


def _collect_posix_shell_env(home: Path | None, names: set[str] | None) -> dict[str, str]:
    if home is None:
        return {}
    env: dict[str, str] = {}
    for filename in _SHELL_ENV_FILES:
        _fill_missing(env, _parse_shell_env_file(home / filename, names), names)
    return env


def _collect_etc_environment(names: set[str] | None) -> dict[str, str]:
    return _parse_shell_env_file(Path("/etc/environment"), names)


def _parse_shell_env_file(path: Path, names: set[str] | None) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    env: dict[str, str] = {}
    for raw_line in text.splitlines():
        for name, value in _parse_shell_env_line(raw_line).items():
            if _wanted(name, names) and name not in env:
                env[name] = value
    return env


def _parse_shell_env_line(raw_line: str) -> dict[str, str]:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#"):
        return {}
    try:
        tokens = shlex.split(stripped, comments=True, posix=True)
    except ValueError:
        tokens = []
    if not tokens:
        return _parse_simple_env_assignment(stripped)
    if tokens[0] == "export":
        tokens = tokens[1:]

    env: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            continue
        name, value = token.split("=", 1)
        name = name.strip()
        if _ENV_NAME_PATTERN.fullmatch(name):
            env[name] = value
    return env


def _parse_simple_env_assignment(line: str) -> dict[str, str]:
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return {}
    name, value = line.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not _ENV_NAME_PATTERN.fullmatch(name):
        return {}
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return {name: value}


def _collect_macos_launchctl_env(names: set[str] | None) -> dict[str, str]:
    try:
        completed = subprocess.run(
            ["launchctl", "export"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}
    if completed.returncode != 0:
        return {}

    env: dict[str, str] = {}
    for raw_line in str(completed.stdout or "").splitlines():
        for name, value in _parse_shell_env_line(raw_line).items():
            if _wanted(name, names) and name not in env:
                env[name] = value
    return env


def _collect_windows_env(names: set[str] | None) -> dict[str, str]:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return {}

    env: dict[str, str] = {}
    for root_name, subkey in _WINDOWS_ENV_KEYS:
        root = getattr(winreg, root_name, None)
        if root is None:
            continue
        key = None
        try:
            key = winreg.OpenKey(root, subkey)
            index = 0
            while True:
                try:
                    name, value, _value_type = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1
                normalized_name = str(name).strip()
                if _wanted(normalized_name, names) and normalized_name not in env and isinstance(value, str):
                    env[normalized_name] = value
        except OSError:
            continue
        finally:
            close_key = getattr(winreg, "CloseKey", None)
            if key is not None and callable(close_key):
                try:
                    close_key(key)
                except OSError:
                    pass
    return env


__all__ = ["collect_publish_process_env", "url_proxy_os_fallback_names"]
