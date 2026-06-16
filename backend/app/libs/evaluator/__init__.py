"""Evaluator 实现包。

注册评估实现：

- basic      — BasicEvaluator（hit_rate / mrr / ndcg，无外部依赖）
- ragas      — RagasEvaluator（faithfulness / answer_relevancy / context_precision / context_recall，使用 ragas 库）
- composite  — CompositeEvaluator（组合多个评估器并加权聚合）

后续可扩展：
- deepeval   — DeepEvalEvaluator（待实现）
"""

from app.libs.evaluator.basic import BasicEvaluator, EvaluatorError  # noqa: F401
from app.libs.evaluator.ragas_evaluator import RagasEvaluator  # noqa: F401
from app.libs.evaluator.composite import CompositeEvaluator  # noqa: F401
from app.libs.evaluator.runner import EvalRunner  # noqa: F401

__all__ = [
    "BasicEvaluator",
    "RagasEvaluator",
    "CompositeEvaluator",
    "EvalRunner",
    "EvaluatorError",
]
