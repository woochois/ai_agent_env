"""Tool Agent 플러그인 패키지.

이 패키지 하위에 규약을 따르는 서브패키지를 추가하면, 프레임워크 레지스트리가
자동으로 발견하여 등록합니다 (auto-discovery).

새 Tool Agent를 만드는 방법:
    1. ``python scripts/new_agent.py <agent_name>`` 으로 스캐폴딩 생성, 또는
    2. 수동으로 ``app/tool_agents/<agent_name>/`` 디렉토리에
       ``__init__.py``, ``tool.py``, ``factory.py``(get_factory 노출) 작성.

규약: 각 서브패키지의 ``factory.py``는 ``get_factory() -> BaseToolFactory``를
노출해야 합니다.
"""
