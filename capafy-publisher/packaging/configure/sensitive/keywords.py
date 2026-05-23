from __future__ import annotations

import re


EXPLICIT_VALUE_SUBSTRINGS = (
    "accesskeyid",
    "secretaccesskey",
    "sessiontoken",
    "webhook",
    "webhooksecret",
    "callbackurl",
    "databaseurl",
    "dburl",
    "dsn",
    "connectionstring",
    "mongodburi",
    "redisurl",
    "redisuri",
    "baseurl",
    "endpoint",
    "proxy",
    "internalurl",
    "intraneturl",
    "appid",
    "appleid",
    "googleid",
    "appsecret",
    "clientid",
    "clientsecret",
    "tenantkey",
    "tenantid",
    "bottoken",
    "accountsid",
    "jwtsecret",
    "sessionsecret",
    "cookiesecret",
    "signingsecret",
)


EXPLICIT_VALUE_EXACT_KEYS = {
    "accesskeyid",
    "secretaccesskey",
    "sessiontoken",
    "awsaccesskeyid",
    "awssecretaccesskey",
    "awssessiontoken",
    "dbhost",
    "dbport",
    "dbname",
    "dbuser",
    "dbusername",
    "dbpassword",
    "dbpass",
    "databasehost",
    "databaseport",
    "databasename",
    "databaseuser",
    "databaseusername",
    "databasepassword",
    "databasepass",
    "mongodburi",
    "redisurl",
    "redisuri",
    "appid",
    "appleid",
    "googleid",
    "clientid",
    "clientsecret",
    "tenantkey",
    "tenantid",
    "accountsid",
    "twilioaccountsid",
    "twilioapikey",
    "twilioapikeysecret",
    "jwtsecret",
    "sessionsecret",
    "cookiesecret",
    "signingsecret",
    "webhooksecret",
    "internalurl",
    "intraneturl",
}
LOGIN_IDENTIFIER_EXACT_KEYS = {
    "username",
    "userid",
    "login",
    "loginid",
    "loginname",
    "loginaccount",
    "account",
    "accountid",
    "accountname",
    "email",
    "mail",
    "phone",
    "phonenumber",
    "mobile",
    "mobilenumber",
    "telephone",
    "tel",
}


def normalize_key_name(key: str) -> str:
    return key.lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")


def key_tokens(key: str) -> list[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", key)
    separated = re.sub(r"[^A-Za-z0-9]+", " ", separated)
    return [token.lower() for token in separated.split() if token]


_PASSWORD_SECRET_NORMALIZED_EXACT = {
    "password",
    "passwd",
    "pwd",
    "pass",
    "passphrase",
    "passcode",
    "dbpass",
    "databasepass",
}
_PASSWORD_SECRET_NORMALIZED_SUBSTRINGS = ("password", "passwd", "passphrase")
_SECRET_NORMALIZED_EXACT = {
    "token",
    "secret",
    "serct",
    "authorization",
    "auth",
    "credential",
    "credentials",
    "creds",
    *_PASSWORD_SECRET_NORMALIZED_EXACT,
}


_SECRET_TOKEN_RULES: list[tuple[frozenset[str], frozenset[str] | None]] = [
    (frozenset({"password"}), None),
    (frozenset({"passwd"}),   None),
    (frozenset({"pwd"}),      None),
    (frozenset({"passphrase"}), None),
    (frozenset({"pass", "phrase"}), None),
    (frozenset({"credential"}), None),
    (frozenset({"credentials"}), None),
    (frozenset({"creds"}), None),
    (frozenset({"api", "key"}),  None),
    (frozenset({"api", "keys"}), None),
    (frozenset({"api", "token"}), None),
    (frozenset({"access", "token"}),  None),
    (frozenset({"auth", "token"}),    None),
    (frozenset({"bot", "token"}),     None),
    (frozenset({"session", "token"}), None),
    (frozenset({"secret", "key"}),     None),
    (frozenset({"client", "secret"}),  None),
    (frozenset({"app", "secret"}),     None),
    (frozenset({"session", "secret"}), None),
    (frozenset({"cookie", "secret"}),  None),
    (frozenset({"jwt", "secret"}),     None),
    (frozenset({"signing", "secret"}), None),
    (frozenset({"webhook", "secret"}), None),
    (frozenset({"private", "key"}), None),

    (frozenset({"live", "key"}), frozenset({"openai", "anthropic", "gemini", "google"})),
]


def is_password_secret_key(key: str) -> bool:
    normalized = normalize_key_name(key)
    if normalized in _PASSWORD_SECRET_NORMALIZED_EXACT:
        return True
    return any(part in normalized for part in _PASSWORD_SECRET_NORMALIZED_SUBSTRINGS)


def contains_explicit_secret_keyword(key: str) -> bool:
    token_set = set(key_tokens(key))
    normalized = normalize_key_name(key)
    if normalized in _SECRET_NORMALIZED_EXACT or is_password_secret_key(key):
        return True
    for required, optional_any in _SECRET_TOKEN_RULES:
        if required <= token_set and (optional_any is None or token_set & optional_any):
            return True
    return False


_VALUE_TOKEN_RULES: list[frozenset[str]] = [
    frozenset({"base", "url"}),
    frozenset({"callback", "url"}),
    frozenset({"internal", "url"}),
    frozenset({"intranet", "url"}),
    frozenset({"client", "id"}),
    frozenset({"client", "secret"}),
    frozenset({"app", "id"}),
    frozenset({"app", "secret"}),
    frozenset({"tenant", "id"}),
    frozenset({"tenant", "key"}),
    frozenset({"database", "url"}),
    frozenset({"db", "url"}),
    frozenset({"bot", "token"}),
    frozenset({"access", "key", "id"}),
    frozenset({"secret", "access", "key"}),
    frozenset({"account", "sid"}),
    frozenset({"mongo", "uri"}),
    frozenset({"mongodb", "uri"}),
    frozenset({"redis", "url"}),
    frozenset({"redis", "uri"}),
    frozenset({"private", "key"}),
]


def contains_explicit_value_keyword(key: str) -> bool:
    lowered = normalize_key_name(key)
    if lowered in EXPLICIT_VALUE_EXACT_KEYS:
        return True
    tokens = set(key_tokens(key))
    if any(rule <= tokens for rule in _VALUE_TOKEN_RULES):
        return True
    return any(keyword in lowered for keyword in EXPLICIT_VALUE_SUBSTRINGS)


_LOGIN_TOKEN_RULES: list[frozenset[str]] = [
    frozenset({"user", "name"}),
    frozenset({"user", "id"}),
    frozenset({"login", "name"}),
    frozenset({"login", "id"}),
    frozenset({"login", "account"}),
    frozenset({"account", "name"}),
    frozenset({"account", "id"}),
    frozenset({"phone", "number"}),
    frozenset({"mobile", "number"}),
]


def contains_login_identifier_keyword(key: str) -> bool:
    lowered = normalize_key_name(key)
    if lowered in LOGIN_IDENTIFIER_EXACT_KEYS:
        return True
    tokens = set(key_tokens(key))
    return any(rule <= tokens for rule in _LOGIN_TOKEN_RULES)


def is_database_setting_key(key: str) -> bool:
    normalized = normalize_key_name(key)
    return normalized.startswith("db") or normalized.startswith("database")


__all__ = [
    "contains_explicit_secret_keyword",
    "contains_explicit_value_keyword",
    "contains_login_identifier_keyword",
    "is_database_setting_key",
    "is_password_secret_key",
    "key_tokens",
    "normalize_key_name",
]
