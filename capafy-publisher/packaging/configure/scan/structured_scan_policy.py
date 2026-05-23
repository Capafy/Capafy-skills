from __future__ import annotations

from pathlib import PurePosixPath

from packaging._shared.common.constants import DSN_VALUE_PATTERN
from packaging.configure.exclusion import SPECIAL_SCAN_PATH_SUFFIXES
from packaging.configure.sensitive.keywords import (
    contains_login_identifier_keyword,
    is_database_setting_key,
    normalize_key_name,
)

from .special_files import XML_SCAN_BASENAMES


STRUCTURED_SCAN_SUFFIXES = {
    ".json",
    ".jsonc",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
    ".sh",
    ".bash",
    ".zsh",
}
STRUCTURED_SCAN_BASENAMES = {
    ".env",
    ".dockercfg",
    ".git-credentials",
    ".netrc",
    "_netrc",
    ".npmrc",
    ".pypirc",
    ".s3cfg",
    "credentials.tfrc.json",
    "env",
    "kubeconfig",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def infer_assignment_service(relpath: str, key: str, value: str) -> str:
    haystack = f"{relpath} {key} {value}".lower()
    normalized_key = normalize_key_name(key)
    if relpath.lower().endswith(".aws/credentials"):
        return "AWS"
    if relpath.lower().endswith(".docker/config.json"):
        return "Docker"
    if relpath.lower().endswith(".dockercfg"):
        return "Docker"
    if relpath.lower().endswith(".gem/credentials"):
        return "RubyGems"
    if relpath.lower().endswith(".kube/config") or relpath.lower().endswith("kubeconfig"):
        return "Kubernetes"
    if relpath.lower().endswith(".m2/settings.xml"):
        return "Maven"
    if relpath.lower().endswith("nuget.config"):
        return "NuGet"
    if relpath.lower().endswith("auth.json"):
        return "Composer"
    if relpath.lower().endswith("credentials.tfrc.json"):
        return "Terraform"
    if relpath.lower().endswith(".s3cfg"):
        return "S3"
    if relpath.lower().endswith(".git-credentials"):
        return "Git"
    if relpath.lower().endswith(".netrc") or relpath.lower().endswith("_netrc"):
        return "Login"
    if "aws" in haystack or "amazon" in haystack:
        return "AWS"
    if "stripe" in haystack:
        return "Stripe"
    if "twilio" in haystack:
        return "Twilio"
    if "pypi" in haystack:
        return "PyPI"
    if "npm" in haystack:
        return "npm"
    if any(token in haystack for token in ("telegram", "tg_bot", "tg-")):
        return "Telegram"
    if any(token in haystack for token in ("feishu", "lark")):
        return "Feishu"
    if "qqbot" in haystack:
        return "QQBot"
    if "slack" in haystack:
        return "Slack"
    if "discord" in haystack:
        return "Discord"
    if "webhook" in haystack:
        return "Webhook"
    if "mongodb" in haystack or "mongo" in haystack:
        return "MongoDB"
    if "redis" in haystack:
        return "Redis"
    if "database" in haystack or is_database_setting_key(key) or DSN_VALUE_PATTERN.match(value.strip()):
        return "Database"
    if any(token in normalized_key for token in ("appid", "clientid", "tenantid", "tenantkey")):
        return "AppId"
    if contains_login_identifier_keyword(key):
        return "Login"
    return key


def should_scan_structured_values(relpath: str) -> bool:
    pure = PurePosixPath(relpath)
    basename = pure.name.lower()
    lowered = relpath.lower()
    if basename in STRUCTURED_SCAN_BASENAMES or basename.startswith(".env."):
        return True
    if basename in XML_SCAN_BASENAMES:
        return True
    if any(lowered.endswith(suffix) for suffix in SPECIAL_SCAN_PATH_SUFFIXES):
        return True
    return pure.suffix.lower() in STRUCTURED_SCAN_SUFFIXES


__all__ = [
    "STRUCTURED_SCAN_BASENAMES",
    "STRUCTURED_SCAN_SUFFIXES",
    "infer_assignment_service",
    "should_scan_structured_values",
]
