"""Test logging setup (KB-5.9 — trả TD-18): level có tác dụng thật, không nhân đôi handler."""

import logging

import pytest

from app.core.logging_setup import LOG_FORMAT, NOISY_LOGGERS, configure_logging, resolve_level


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """Trả root logger về trạng thái cũ để test khác không bị ảnh hưởng."""
    root = logging.getLogger()
    before_handlers = list(root.handlers)
    before_level = root.level
    yield
    root.handlers = before_handlers
    root.setLevel(before_level)
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("DEBUG", logging.DEBUG),
        ("info", logging.INFO),
        (" warning ", logging.WARNING),
        ("20", 20),
        ("không-phải-level", logging.INFO),
        ("", logging.INFO),
        (None, logging.INFO),
    ],
)
def test_resolve_level(raw, expected):
    assert resolve_level(raw) == expected


def test_handler_is_added_once():
    configure_logging("INFO")
    configure_logging("INFO")

    ours = [h for h in logging.getLogger().handlers if getattr(h, "name", None) == "kb-console"]
    assert len(ours) == 1


def test_info_visible_at_info_level(caplog):
    """Đây chính là bug TD-18: trước đây `logger.info` của `app.*` không hiện."""
    configure_logging("INFO")
    caplog.set_level(logging.INFO)

    logging.getLogger("app.services.chat_service").info("multi-query: 2 phần, 3 hit")

    assert "multi-query: 2 phần, 3 hit" in caplog.text


def test_info_hidden_at_warning_level():
    configure_logging("WARNING")
    app_logger = logging.getLogger("app.services.chat_service")

    assert app_logger.getEffectiveLevel() == logging.WARNING


def test_noisy_loggers_downgraded():
    configure_logging("DEBUG")

    for name in NOISY_LOGGERS:
        assert logging.getLogger(name).level >= logging.WARNING


def test_format_has_no_placeholder_for_pii():
    """Format không chèn gì ngoài level/name/message — tránh vô tình log payload."""
    assert LOG_FORMAT == "%(levelname)s %(name)s: %(message)s"
