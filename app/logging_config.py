"""JSON 구조화 로깅 설정 모듈.

python-json-logger를 사용하여 JSON 형식 로그를 출력합니다.
콘솔(stdout)과 파일(RotatingFileHandler) 두 가지 핸들러를 설정합니다.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.6
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from pythonjsonlogger.json import JsonFormatter


# 유효한 로그 레벨 목록
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}

# 로그 파일 설정
LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs"))
LOG_FILE = os.path.join(LOG_DIR, "agent.log")
MAX_BYTES = 50 * 1024 * 1024  # 50MB
BACKUP_COUNT = 5


def _get_log_level() -> str:
    """환경 변수 LOG_LEVEL에서 로그 레벨을 가져옵니다.

    유효하지 않은 값이면 경고를 출력하고 INFO를 반환합니다.

    Returns:
        str: 유효한 로그 레벨 문자열 (DEBUG, INFO, WARNING, ERROR 중 하나)
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    if log_level not in VALID_LOG_LEVELS:
        print(
            f"WARNING: Invalid LOG_LEVEL '{log_level}'. "
            f"Must be one of {sorted(VALID_LOG_LEVELS)}. Defaulting to INFO.",
            file=sys.stderr,
        )
        return "INFO"

    return log_level


def _create_json_formatter() -> JsonFormatter:
    """JSON 포맷터를 생성합니다.

    로그 항목에 timestamp, level, message 기본 필드를 포함합니다.

    Returns:
        JsonFormatter: 설정된 JSON 포맷터 인스턴스
    """
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    return formatter


def setup_logging(log_level: Optional[str] = None) -> None:
    """루트 로거에 JSON 구조화 로깅을 설정합니다.

    콘솔(stdout)과 파일(RotatingFileHandler) 핸들러를 구성하여
    모든 로그를 JSON 형식으로 출력합니다.

    Args:
        log_level: 로그 레벨 문자열 (DEBUG, INFO, WARNING, ERROR).
                   None이면 환경 변수 LOG_LEVEL을 사용합니다.
    """
    if log_level is None:
        log_level = _get_log_level()
    else:
        log_level = log_level.upper()
        if log_level not in VALID_LOG_LEVELS:
            print(
                f"WARNING: Invalid log_level '{log_level}'. "
                f"Must be one of {sorted(VALID_LOG_LEVELS)}. Defaulting to INFO.",
                file=sys.stderr,
            )
            log_level = "INFO"

    # logs 디렉토리 생성
    os.makedirs(LOG_DIR, exist_ok=True)

    # JSON 포맷터 설정
    formatter = _create_json_formatter()

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # 콘솔 핸들러 (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (RotatingFileHandler: 50MB, 최대 5개 백업 파일)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
