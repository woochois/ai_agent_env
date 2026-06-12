"""Calculator Agent Tool 구현.

Python의 ``ast`` 모듈로 산술식을 안전하게 파싱/평가합니다. ``eval``을 직접
사용하지 않으므로 임의 코드 실행 위험이 없습니다.
"""

from __future__ import annotations

import ast
import operator
from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact

AGENT_TYPE = "calculator_agent"

# 허용된 연산자만 매핑 (안전한 평가)
_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_eval(expression: str) -> float:
    """산술식을 안전하게 평가합니다.

    숫자, 사칙연산(+,-,*,/,//,%,**), 괄호, 단항 부호만 허용합니다.

    Args:
        expression: 평가할 산술식 (예: "2 + 3 * (4 - 1)").

    Returns:
        계산 결과(float).

    Raises:
        ValueError: 허용되지 않은 토큰/연산이 포함된 경우.
        ZeroDivisionError: 0으로 나누는 경우.
    """
    try:
        node = ast.parse(expression, mode="eval").body
    except SyntaxError as exc:
        raise ValueError(f"잘못된 수식입니다: {expression}") from exc
    return _eval_node(node)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("숫자만 사용할 수 있습니다")
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise ValueError(f"허용되지 않은 연산자입니다: {op_type.__name__}")
        return _BINARY_OPS[op_type](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"허용되지 않은 단항 연산자입니다: {op_type.__name__}")
        return _UNARY_OPS[op_type](_eval_node(node.operand))
    raise ValueError("허용되지 않은 표현식입니다")


class CalculatorToolInput(BaseModel):
    """Calculator Tool 입력 스키마."""

    expression: str = Field(
        ..., description="평가할 산술식 (예: '2 + 3 * (4 - 1)')"
    )


class CalculatorTool(BaseAgentTool):
    """산술식을 안전하게 계산하는 Tool."""

    name: str = "calculator"
    description: str = (
        "산술식을 계산합니다. 사칙연산(+,-,*,/), 거듭제곱(**), 괄호를 지원합니다. "
        "예: '120 * 0.85', '(3 + 5) / 2'"
    )
    args_schema: type[BaseModel] = CalculatorToolInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(self, expression: str, config: RunnableConfig | None = None):
        return self._calculate(expression)

    async def _arun(self, expression: str, config: RunnableConfig | None = None):
        return self._calculate(expression)

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="계산 중 오류가 발생했습니다",
        result=None,
    )
    def _calculate(self, expression: str) -> tuple[str, dict]:
        result = safe_eval(expression)
        artifact = build_artifact(AGENT_TYPE, expression=expression, result=result)
        return str(result), artifact

    def format_content(self, message: ToolMessage) -> ToolMessage:
        if isinstance(message.artifact, dict) and "error_message" not in message.artifact:
            expr = message.artifact.get("expression", "")
            result = message.artifact.get("result")
            return message.model_copy(update={"content": f"{expr} = {result}"})
        return message
