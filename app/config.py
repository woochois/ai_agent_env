"""환경 변수 로드 및 검증 모듈.

Pydantic Settings를 사용하여 .env 파일에서 환경 변수를 로드하고,
필수 변수 존재 여부와 유효성을 검증합니다.
"""

import sys
import warnings
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class Settings(BaseSettings):
    """애플리케이션 환경 변수 설정.

    필수 변수:
        OPENAI_API_KEY: LLM API 키
        DATABASE_URL: PostgreSQL 연결 문자열
        ELASTICSEARCH_URL: Elasticsearch 연결 URL

    선택 변수:
        LOG_LEVEL: 로그 레벨 (DEBUG|INFO|WARNING|ERROR), 기본값 INFO
        DEBUG_MODE: 디버거 활성화 여부, 기본값 False
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 필수 변수 - 기본값을 빈 문자열로 설정하여 pydantic이 누락 시에도 객체를 생성하도록 함
    # 실제 검증은 model_validator에서 수행
    OPENAI_API_KEY: str = ""
    DATABASE_URL: str = ""
    ELASTICSEARCH_URL: str = ""

    # 선택 변수
    LOG_LEVEL: str = "INFO"
    DEBUG_MODE: bool = False

    @model_validator(mode="after")
    def validate_required_and_log_level(self) -> "Settings":
        """필수 환경 변수와 LOG_LEVEL 유효성을 검증합니다.

        - 필수 변수가 누락되었거나 빈 문자열이면 모든 누락 변수명을 수집하여 에러를 발생시킵니다.
        - LOG_LEVEL이 유효하지 않으면 경고 출력 후 INFO로 대체합니다.
        """
        # 필수 변수 검증: 빈 문자열도 누락으로 간주
        required_fields = ["OPENAI_API_KEY", "DATABASE_URL", "ELASTICSEARCH_URL"]
        missing = [
            field for field in required_fields
            if not getattr(self, field, "").strip()
        ]

        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(
                f"필수 환경 변수가 누락되었거나 비어 있습니다: [{missing_list}]"
            )

        # LOG_LEVEL 유효성 검증
        if self.LOG_LEVEL.upper() not in VALID_LOG_LEVELS:
            warnings.warn(
                f"LOG_LEVEL '{self.LOG_LEVEL}'은(는) 유효하지 않습니다. "
                f"유효한 값: {VALID_LOG_LEVELS}. 기본값 INFO로 대체합니다.",
                UserWarning,
                stacklevel=2,
            )
            self.LOG_LEVEL = "INFO"
        else:
            # 대소문자 정규화
            self.LOG_LEVEL = self.LOG_LEVEL.upper()

        return self


@lru_cache()
def get_settings() -> Settings:
    """Settings 인스턴스를 생성하고 캐싱합니다.

    환경 변수 검증 실패 시 에러 메시지를 출력하고 서비스를 중단합니다.

    Returns:
        Settings: 검증된 설정 인스턴스

    Raises:
        SystemExit: 필수 환경 변수 누락 시 sys.exit(1) 호출
    """
    try:
        return Settings()
    except Exception as e:
        print(f"[ERROR] 환경 변수 설정 실패: {e}", file=sys.stderr)
        sys.exit(1)
