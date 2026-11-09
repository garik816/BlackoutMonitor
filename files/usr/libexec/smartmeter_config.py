"""Shared UCI configuration and validation for the availability monitor."""

import fcntl
import ipaddress
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit


PACKAGE = "smartmeter-availability"
CONFIG_FILE = Path("/etc/config") / PACKAGE
ID_RE = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
HOST_RE = re.compile(r"[A-Za-z0-9_.:-]{1,253}\Z")
INTERFACE_RE = re.compile(r"[A-Za-z0-9_.:-]{1,32}\Z")
MAC_RE = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\Z")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30).stdout


def read_targets():
    sections = {}
    for line in run("uci", "-q", "show", PACKAGE).splitlines():
        key, _, raw = line.partition("=")
        if not key.startswith(PACKAGE + ".") or not _:
            continue
        try:
            value = shlex.split(raw)[0]
        except (ValueError, IndexError):
            continue
        key = key[len(PACKAGE) + 1:]
        if "." not in key:
            if value == "monitor" and ID_RE.fullmatch(key):
                sections[key] = {"id": key}
        else:
            section, option = key.split(".", 1)
            if section in sections:
                sections[section][option] = value
    return [normalise(target) for target in sections.values()]


def normalise(target):
    item = dict(target)
    ident = item["id"]
    item.setdefault("name", "SmartMeter" if ident == "main" else ident)
    item.setdefault("type", "arp")
    item.setdefault("host", "192.168.1.113" if ident == "main" else "")
    item.setdefault("url", "")
    item.setdefault("interface", "br-lan")
    item.setdefault("mac", "")
    item.setdefault("interval", "15")
    item.setdefault("timeout", "5")
    item.setdefault("expected_status", "200")
    item.setdefault("retention_days", "365" if ident == "main" else "30")
    item.setdefault("enabled", "1")
    item.setdefault("database", database_path(ident))
    return item


def database_path(ident):
    return ("/root/smartmeter-availability.sqlite3" if ident == "main"
            else f"/root/smartmeter-{ident}.sqlite3")


def public_target(target):
    return {key: value for key, value in target.items() if key != "database"}


def bounded_int(value, name, minimum, maximum):
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError(f"{name}: требуется число {minimum}–{maximum}")
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{name}: допустимо {minimum}–{maximum}")
    return str(number)


def validate_targets(payload, old_targets):
    if not isinstance(payload, list) or not 1 <= len(payload) <= 30:
        raise ValueError("Нужно задать от 1 до 30 проверок")
    old_by_id = {item["id"]: item for item in old_targets}
    seen = set()
    result = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("Некорректная запись проверки")
        ident = str(raw.get("id", ""))
        if not ID_RE.fullmatch(ident) or ident in seen:
            raise ValueError("Идентификатор проверки некорректен или повторяется")
        seen.add(ident)
        name = str(raw.get("name", "")).strip()
        if not 1 <= len(name) <= 80 or any(ord(c) < 32 for c in name):
            raise ValueError(f"{ident}: название должно содержать 1–80 символов")
        kind = str(raw.get("type", ""))
        if kind not in ("arp", "icmp", "http"):
            raise ValueError(f"{name}: неизвестный тип проверки")
        host = str(raw.get("host", "")).strip()
        url = str(raw.get("url", "")).strip()
        interface = str(raw.get("interface", "br-lan")).strip()
        mac = str(raw.get("mac", "")).strip().lower()
        if kind == "arp":
            try:
                ipaddress.IPv4Address(host)
            except ipaddress.AddressValueError as exc:
                raise ValueError(f"{name}: для ARP нужен IPv4-адрес") from exc
            if not INTERFACE_RE.fullmatch(interface):
                raise ValueError(f"{name}: некорректный сетевой интерфейс")
            if mac and not MAC_RE.fullmatch(mac):
                raise ValueError(f"{name}: некорректный MAC-адрес")
        elif kind == "icmp":
            if not HOST_RE.fullmatch(host):
                raise ValueError(f"{name}: некорректный адрес для ping")
        else:
            if len(url) > 2048 or any(ord(c) <= 32 for c in url):
                raise ValueError(f"{name}: некорректный URL")
            try:
                parsed = urlsplit(url)
                if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError()
                _ = parsed.port
            except ValueError as exc:
                raise ValueError(f"{name}: нужен корректный HTTP/HTTPS URL без учётных данных") from exc
        enabled = str(raw.get("enabled", "1"))
        if enabled not in ("0", "1"):
            raise ValueError(f"{name}: некорректный флаг включения")
        result.append({
            "id": ident, "name": name, "type": kind, "host": host, "url": url,
            "interface": interface, "mac": mac, "enabled": enabled,
            "interval": bounded_int(raw.get("interval", "15"), f"{name}: интервал", 5, 3600),
            "timeout": bounded_int(raw.get("timeout", "5"), f"{name}: тайм-аут", 1, 60),
            "expected_status": bounded_int(raw.get("expected_status", "200"), f"{name}: HTTP-код", 100, 599),
            "retention_days": bounded_int(raw.get("retention_days", "30"), f"{name}: хранение", 1, 3650),
            "database": old_by_id.get(ident, {}).get("database", database_path(ident)),
        })
    return result


def save_targets(payload):
    lock = Path("/var/lock/smartmeter-availability-config.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        previous = read_targets()
        if not isinstance(payload, dict) or not isinstance(payload.get("remove_ids"), list):
            raise ValueError("Обновите страницу мониторинга перед сохранением")
        removed = payload["remove_ids"]
        if any(not isinstance(ident, str) or not ID_RE.fullmatch(ident) for ident in removed):
            raise ValueError("Некорректный список удаляемых проверок")
        if len(removed) != len(set(removed)):
            raise ValueError("Некорректный список удаляемых проверок")
        targets = validate_targets(payload.get("targets"), previous)
        old_ids = {item["id"] for item in previous}
        new_ids = {item["id"] for item in targets}
        if old_ids - new_ids != set(removed) or set(removed) & new_ids:
            raise ValueError("Список проверок изменился. Обновите страницу и повторите сохранение")
        backup_fd, backup_name = tempfile.mkstemp(prefix="smartmeter-availability.", dir="/etc/config")
        os.close(backup_fd)
        shutil.copy2(CONFIG_FILE, backup_name)
        try:
            for old in previous:
                run("uci", "-q", "delete", f"{PACKAGE}.{old['id']}")
            for target in targets:
                ident = target["id"]
                run("uci", "set", f"{PACKAGE}.{ident}=monitor")
                for key, value in target.items():
                    if key != "id":
                        run("uci", "set", f"{PACKAGE}.{ident}.{key}={value}")
            run("uci", "commit", PACKAGE)
            os.chmod(CONFIG_FILE, 0o600)
            run("/etc/init.d/smartmeter-availability", "restart")
        except Exception:
            subprocess.run(["uci", "-q", "revert", PACKAGE], capture_output=True, timeout=10)
            shutil.copy2(backup_name, CONFIG_FILE)
            subprocess.run(["/etc/init.d/smartmeter-availability", "restart"],
                           capture_output=True, timeout=30)
            raise
        finally:
            os.unlink(backup_name)
        return [public_target(target) for target in targets]
