"""app/config.py 환경 변수 설정 모듈 테스트."""

import sys
import warnings
from unittest.mock import patch

import pytest

from app.config import Settings, VALID_LOG_LEVELS, get_settings


class TestSettingsRequiredVariables:
    """필수 환경 변수 검증 테스트."""

    def test_all_required_present(self, monkeypatch):
        """필수 변수가 모두 존재하면 Settings 생성 성공."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/testdb")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")

        settings = Settings(_env_file=None)

        assert settings.OPENAI_API_KEY == "sk-test-key-123"
        assert settings.DATABASE_URL == "postgresql://user:pass@db:5432/testdb"
        assert settings.ELASTICSEARCH_URL == "http://elasticsearch:9200"

    def test_missing_single_required_variable(self, monkeypatch):
        """필수 변수 하나 누락 시 에러 발생."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/testdb")
        monkeypatch.delenv("ELASTICSEARCH_URL", raising=False)

        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

        assert "ELASTICSEARCH_URL" in str(exc_info.value)

    def test_missing_multiple_required_variables(self, monkeypatch):
        """필수 변수 여러 개 누락 시 모든 누락 변수명을 에러에 포함."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("ELASTICSEARCH_URL", raising=False)

        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

        error_msg = str(exc_info.value)
        assert "OPENAI_API_KEY" in error_msg
        assert "DATABASE_URL" in error_msg
        assert "ELASTICSEARCH_URL" in error_msg

    def test_empty_string_treated_as_missing(self, monkeypatch):
        """빈 문자열은 누락으로 처리."""
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/testdb")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")

        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

        assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_whitespace_only_treated_as_missing(self, monkeypatch):
        """공백만 있는 값도 누락으로 처리."""
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/testdb")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")

        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

        assert "OPENAI_API_KEY" in str(exc_info.value)


class TestSettingsLogLevel:
    """LOG_LEVEL 유효성 검증 테스트."""

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    def test_valid_log_levels(self, monkeypatch, level):
        """유효한 LOG_LEVEL 값은 그대로 사용."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")
        monkeypatch.setenv("LOG_LEVEL", level)

        settings = Settings(_env_file=None)
        assert settings.LOG_LEVEL == level

    def test_log_level_case_insensitive(self, monkeypatch):
        """LOG_LEVEL은 대소문자 구분 없이 인식."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        settings = Settings(_env_file=None)
        assert settings.LOG_LEVEL == "DEBUG"

    def test_invalid_log_level_falls_back_to_info(self, monkeypatch):
        """유효하지 않은 LOG_LEVEL은 경고 후 INFO로 대체."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")
        monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            settings = Settings(_env_file=None)

            assert settings.LOG_LEVEL == "INFO"
            assert len(w) == 1
            assert "VERBOSE" in str(w[0].message)

    def test_default_log_level_is_info(self, monkeypatch):
        """LOG_LEVEL 미설정 시 기본값 INFO."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        settings = Settings(_env_file=None)
        assert settings.LOG_LEVEL == "INFO"


class TestSettingsDebugMode:
    """DEBUG_MODE 설정 테스트."""

    def test_default_debug_mode_is_false(self, monkeypatch):
        """DEBUG_MODE 미설정 시 기본값 False."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")
        monkeypatch.delenv("DEBUG_MODE", raising=False)

        settings = Settings(_env_file=None)
        assert settings.DEBUG_MODE is False

    def test_debug_mode_true(self, monkeypatch):
        """DEBUG_MODE=true 설정."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")
        monkeypatch.setenv("DEBUG_MODE", "true")

        settings = Settings(_env_file=None)
        assert settings.DEBUG_MODE is True


class TestGetSettings:
    """get_settings() 함수 테스트."""

    def test_get_settings_exits_on_missing_vars(self, monkeypatch):
        """필수 변수 누락 시 sys.exit(1) 호출."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("ELASTICSEARCH_URL", raising=False)

        # lru_cache 초기화
        get_settings.cache_clear()

        # get_settings 내부에서 Settings()를 호출할 때 .env를 읽지 않도록 패치
        original_init = Settings.__init__

        def patched_init(self, **kwargs):
            kwargs.setdefault("_env_file", None)
            original_init(self, **kwargs)

        with patch.object(Settings, "__init__", patched_init):
            with pytest.raises(SystemExit) as exc_info:
                get_settings()

        assert exc_info.value.code == 1
        get_settings.cache_clear()

    def test_get_settings_returns_valid_settings(self, monkeypatch):
        """유효한 환경 시 Settings 인스턴스 반환."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")

        # lru_cache 초기화
        get_settings.cache_clear()

        settings = get_settings()
        assert isinstance(settings, Settings)
        assert settings.OPENAI_API_KEY == "sk-test-key"

        # 캐시 정리
        get_settings.cache_clear()

    def test_get_settings_caches_result(self, monkeypatch):
        """get_settings()는 결과를 캐싱한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/db")
        monkeypatch.setenv("ELASTICSEARCH_URL", "http://es:9200")

        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

        get_settings.cache_clear()
