"""Evaluator 实现包 — 导入即触发工厂注册。"""

from app.libs.evaluator.basic import BasicEvaluator
from app.libs.factory import EvaluatorFactory

# ── 注册默认实现 ────────────────────────────────────────────

EvaluatorFactory.register("custom_metrics", BasicEvaluator)
EvaluatorFactory.register("ragas", BasicEvaluator)

__all__ = ["BasicEvaluator"]
