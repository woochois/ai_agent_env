"""app/logging_config.py JSON 구조화 로깅 설정 모듈 테스트."""

import json
import logging
import os
import tempfile
from io import StringIO
from unittest.mock import patch

import pytest

from app.logging_config import (
    BACKUP_COUNT,
    LOG_DIR,
    MAX_BYTES,
    VALID_LOG_LEVELS,
    _create_json_formatter,
    _get_log_level,
    setup_logging,
)


class TestGetLogLevel:
    """_get_log_level() 함수 테스트."""

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    def test_valid_log_levels(self, monkeypatch, level):
        """유효한 LOG_LEVEL 값은 그대로 반환."""
        monkeypatch.setenv("LOG_LEVEL", level)
        assert _get_log_level() == level

    def test_default_is_info(self, monkeypatch):
        """LOG_LEVEL 미설정 시 기본값 INFO."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert _get_log_level() == "INFO"

    def test_case_insensitive(self, monkeypatch):
        """대소문자 구분 없이 인식."""
        monkeypatch.setenv("LOG_LEVEL", "debug")
        assert _get_log_level() == "DEBUG"

    def test_invalid_level_returns_info_with_warning(self, monkeypatch, capsys):
        """유효하지 않은 값은 stderr 경고 출력 후 INFO 반환."""
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")
        result = _get_log_level()

        assert result == "INFO"
        captured = capsys.readouterr()
        assert "VERBOSE" in captured.err
        assert "WARNING" in captured.err


class TestCreateJsonFormatter:
    """_create_json_formatter() 함수 테스트."""

    def test_formatter_produces_valid_json(self):
        """포맷터가 유효한 JSON을 생성한다."""
        formatter = _create_json_formatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed

    def test_formatter_includes_correct_level(self):
        """포맷터가 올바른 level 필드를 포함한다."""
        formatter = _create_json_formatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning message",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "WARNING"

    def test_formatter_includes_message(self):
        """포맷터가 message 필드를 포함한다."""
        formatter = _create_json_formatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello world",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["message"] == "Hello world"

    def test_formatter_timestamp_format(self):
        """포맷터가 ISO 형식의 timestamp를 포함한다."""
        formatter = _create_json_formatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Timestamp test",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        # ISO 8601 형식: YYYY-MM-DDTHH:MM:SS
        assert "T" in parsed["timestamp"]
        assert len(parsed["timestamp"]) >= 19  # 최소 "2024-01-01T00:00:00"


class TestSetupLogging:
    """setup_logging() 함수 테스트."""

    def setup_method(self):
        """각 테스트 전 루트 로거 핸들러 초기화."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

    def teardown_method(self):
        """각 테스트 후 루트 로거 핸들러 정리."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

    def test_setup_creates_two_handlers(self, tmp_path, monkeypatch):
        """setup_logging은 콘솔과 파일 핸들러 2개를 생성한다."""
        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        setup_logging("INFO")
        root_logger = logging.getLogger()

        assert len(root_logger.handlers) == 2

    def test_setup_console_handler_is_stdout(self, tmp_path, monkeypatch):
        """콘솔 핸들러는 stdout으로 출력한다."""
        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        setup_logging("INFO")
        root_logger = logging.getLogger()

        console_handler = root_logger.handlers[0]
        assert isinstance(console_handler, logging.StreamHandler)

    def test_setup_file_handler_is_rotating(self, tmp_path, monkeypatch):
        """파일 핸들러는 RotatingFileHandler이다."""
        from logging.handlers import RotatingFileHandler

        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        setup_logging("INFO")
        root_logger = logging.getLogger()

        file_handler = root_logger.handlers[1]
        assert isinstance(file_handler, RotatingFileHandler)

    def test_setup_file_handler_rotation_settings(self, tmp_path, monkeypatch):
        """파일 핸들러의 로테이션 설정이 올바르다 (50MB, 5개 파일)."""
        from logging.handlers import RotatingFileHandler

        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        setup_logging("INFO")
        root_logger = logging.getLogger()

        file_handler = root_logger.handlers[1]
        assert file_handler.maxBytes == 50 * 1024 * 1024  # 50MB
        assert file_handler.backupCount == 5

    def test_setup_respects_log_level(self, tmp_path, monkeypatch):
        """설정한 로그 레벨이 적용된다."""
        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        setup_logging("DEBUG")
        root_logger = logging.getLogger()

        assert root_logger.level == logging.DEBUG

    def test_setup_uses_env_var_when_no_argument(self, tmp_path, monkeypatch):
        """인자 없이 호출 시 환경 변수 LOG_LEVEL을 사용한다."""
        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))
        monkeypatch.setenv("LOG_LEVEL", "WARNING")

        setup_logging()
        root_logger = logging.getLogger()

        assert root_logger.level == logging.WARNING

    def test_setup_invalid_level_argument_defaults_to_info(self, tmp_path, monkeypatch, capsys):
        """유효하지 않은 로그 레벨 인자는 경고 후 INFO로 대체."""
        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        setup_logging("INVALID")
        root_logger = logging.getLogger()

        assert root_logger.level == logging.INFO
        captured = capsys.readouterr()
        assert "INVALID" in captured.err

    def test_setup_creates_log_directory(self, tmp_path, monkeypatch):
        """setup_logging은 로그 디렉토리를 생성한다."""
        log_dir = str(tmp_path / "new_logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        assert not os.path.exists(log_dir)
        setup_logging("INFO")
        assert os.path.exists(log_dir)

    def test_setup_clears_existing_handlers(self, tmp_path, monkeypatch):
        """setup_logging은 기존 핸들러를 제거하여 중복을 방지한다."""
        log_dir = str(tmp_path / "logs")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", os.path.join(log_dir, "agent.log"))

        # 두 번 호출
        setup_logging("INFO")
        setup_logging("DEBUG")
        root_logger = logging.getLogger()

        # 핸들러가 2개만 있어야 함 (중복 없음)
        assert len(root_logger.handlers) == 2

    def test_log_output_is_valid_json(self, tmp_path, monkeypatch):
        """실제 로그 출력이 유효한 JSON이다."""
        log_dir = str(tmp_path / "logs")
        log_file = os.path.join(log_dir, "agent.log")
        monkeypatch.setattr("app.logging_config.LOG_DIR", log_dir)
        monkeypatch.setattr("app.logging_config.LOG_FILE", log_file)

        setup_logging("INFO")
        logger = logging.getLogger("test.json_output")
        logger.info("Test log entry")

        # 파일에 기록된 로그 확인
        with open(log_file, "r") as f:
            line = f.readline().strip()

        parsed = json.loads(line)
        assert parsed["message"] == "Test log entry"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed


class TestLoggingConstants:
    """로깅 상수 값 테스트."""

    def test_max_bytes_is_50mb(self):
        """MAX_BYTES가 50MB이다."""
        assert MAX_BYTES == 50 * 1024 * 1024

    def test_backup_count_is_5(self):
        """BACKUP_COUNT가 5이다."""
        assert BACKUP_COUNT == 5

    def test_valid_log_levels(self):
        """유효한 로그 레벨 집합이 올바르다."""
        assert VALID_LOG_LEVELS == {"DEBUG", "INFO", "WARNING", "ERROR"}
