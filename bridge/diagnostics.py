"""Bounded local diagnostic logging; never log pairing payloads or bot source."""
import json
import logging
from logging.handlers import RotatingFileHandler
import platform
from pathlib import Path
import sys
import threading
from version import RELEASE_TAG

logger = logging.getLogger('mythicwalker')
logger.addHandler(logging.NullHandler())
_secrets = set()
_guard = threading.Lock()
_log_path = None


def hide_secret(value):
    if value:
        with _guard: _secrets.add(str(value))


def scrub(value):
    result = str(value)
    with _guard: secrets = tuple(_secrets)
    for secret in sorted(secrets, key=len, reverse=True):
        result = result.replace(secret, '[REDACTED]')
    return result.replace(str(Path.home()), '%USERPROFILE%')


class SafeFormatter(logging.Formatter):
    def format(self, record): return scrub(super().format(record))


def start_logging(directory):
    global _log_path
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    _log_path = directory / 'bridge.log'
    for handler in list(logger.handlers):
        logger.removeHandler(handler); handler.close()
    handler = RotatingFileHandler(_log_path, maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
    handler.setFormatter(SafeFormatter('%(asctime)s %(levelname)s [%(threadName)s] %(message)s'))
    logger.addHandler(handler); logger.setLevel(logging.DEBUG); logger.propagate = False
    event('startup', release=RELEASE_TAG, python=sys.version.split()[0], platform=sys.platform,
          os=platform.release(), architecture=platform.machine(), frozen=bool(getattr(sys, 'frozen', False)))
    return _log_path


def event(name, **fields):
    logger.debug('%s %s', name, json.dumps(fields, ensure_ascii=False, default=str))


def bundle():
    for handler in logger.handlers: handler.flush()
    logs = []
    if _log_path:
        # Tail only; total export stays below the websocket message limit.
        for suffix in ['.3', '.2', '.1', '']:
            path = Path(str(_log_path) + suffix)
            if path.exists():
                with path.open('rb') as stream:
                    stream.seek(max(0, path.stat().st_size - 160*1024))
                    logs.append({'name':path.name, 'tail':scrub(stream.read().decode('utf-8', errors='replace'))})
    return {'release':RELEASE_TAG, 'logs':logs, 'note':'Local logs only; tokens and bot source are omitted.'}
