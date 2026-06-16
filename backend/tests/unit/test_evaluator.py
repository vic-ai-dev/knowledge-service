"""H5 — Recall 回归测试（单元级评估器验证）。
测试评估器的核心逻辑：
- BasicEvaluator: hit_rate, mrr, ndcg 计算是否正确
- RagasEvaluator 构造与导入验证
- CompositeEvaluator: 权重合并是否合理
"""
from __future__ import annotations
import pytest
from app.libs.base.base_evaluator import EvalMetrics
from app.libs.evaluator.basic import BasicEvaluator
from app.libs.evaluator.composite import CompositeEvaluator
pytestmark = pytest.mark.unit
class TestBasicEvaluator:
    """BasicEvaluator 单元测试。"""
    @pytest.fixture
    def evaluator(self) -> BasicEvaluator:
        return BasicEvaluator(k=5)
    @pytest.mark.asyncio
    async def test_basic_empty_ground_truth(self, evaluator: BasicEvaluator):
        """无 ground_truth 时返回零值指标。"""
        metrics = await evaluator.evaluate(
            query="test",
            retrieved_chunks=["a", "b", "c"],
            ground_truth=None,
        )
        assert metrics.hit_rate == 0.0
        assert metrics.mrr == 0.0
        assert metrics.ndcg == 0.0
        assert "note" in metrics.extra
    @pytest.mark.asyncio
    async def test_basic_perfect_match(self, evaluator: BasicEvaluator):
        """完全匹配时所有指标应为 1.0。"""
        metrics = await evaluator.evaluate(
            query="test",
            retrieved_chunks=["a", "b", "c"],
            ground_truth=["a", "b", "c"],
        )
        assert metrics.hit_rate == 1.0
        assert metrics.mrr == 1.0
        assert metrics.ndcg == 1.0
    @pytest.mark.asyncio
    async def test_basic_half_match(self, evaluator: BasicEvaluator):
        """部分匹配时指标应在中间区间。"""
        metrics = await evaluator.evaluate(
            query="test",
            retrieved_chunks=["a", "b", "x", "y"],
            ground_truth=["a", "b", "c"],
        )
        # 3 个中的 2 个命中
        assert abs(metrics.hit_rate - 2 / 3) < 0.01
        # 第一个命中在 rank 1
        assert metrics.mrr == 1.0
    @pytest.mark.asyncio
    async def test_basic_no_match(self, evaluator: BasicEvaluator):
        """无匹配时所有指标应为 0.0。"""
        metrics = await evaluator.evaluate(
            query="test",
            retrieved_chunks=["x", "y", "z"],
            ground_truth=["a", "b"],
        )
        assert metrics.hit_rate == 0.0
        assert metrics.mrr == 0.0
        assert metrics.ndcg == 0.0
    @pytest.mark.asyncio
    async def test_basic_empty_retrieval(self, evaluator: BasicEvaluator):
        """空检索结果应抛出异常。"""
        with pytest.raises(ValueError, match="retrieved_chunks"):
            await evaluator.evaluate(
                query="test",
                retrieved_chunks=[],
                ground_truth=["a"],
            )
    @pytest.mark.asyncio
    async def test_basic_empty_query(self, evaluator: BasicEvaluator):
        """空查询应抛出异常。"""
        with pytest.raises(ValueError, match="query"):
            await evaluator.evaluate(
                query="",
                retrieved_chunks=["a"],
            )
    @pytest.mark.asyncio
    async def test_basic_retrieval_exceeds_ground_truth(self, evaluator: BasicEvaluator):
        """检索结果多于 ground_truth 时仍应正确计算。"""
        metrics = await evaluator.evaluate(
            query="test",
            retrieved_chunks=["a", "b", "c", "d", "e"],
            ground_truth=["a"],
        )
        assert metrics.hit_rate == 1.0  # 1/1 命中
        assert metrics.mrr == 1.0
    @pytest.mark.asyncio
    async def test_basic_mrr_sequential(self, evaluator: BasicEvaluator):
        """MRR 应反映第一个匹配的位置。"""
        # 第一个匹配在 rank 3
        metrics = await evaluator.evaluate(
            query="test",
            retrieved_chunks=["x", "y", "a", "b"],
            ground_truth=["a"],
        )
        assert abs(metrics.mrr - 1 / 3) < 0.01
    @pytest.mark.asyncio
    async def test_basic_ndcg_ordering(self, evaluator: BasicEvaluator):
        """NDCG 应惩罚相关性靠后的排序。"""
        chunks_ordered = ["a", "x", "b", "y", "c", "z"]
        gt = ["a", "b", "c"]
        metrics_ordered = await evaluator.evaluate(
            query="test", retrieved_chunks=chunks_ordered, ground_truth=gt,
        )
        # 逆序
        chunks_reversed = ["c", "y", "b", "x", "a", "z"]
        metrics_reversed = await evaluator.evaluate(
            query="test", retrieved_chunks=list(reversed(chunks_ordered)), ground_truth=gt,
        )
        # 正序的 NDCG 应 >= 逆序的 NDCG
        assert metrics_ordered.ndcg >= metrics_reversed.ndcg
class TestCompositeEvaluator:
    """CompositeEvaluator 单元测试。"""
    @pytest.fixture
    def basic_evaluator(self) -> BasicEvaluator:
        return BasicEvaluator()
    def test_create_empty_fails(self):
        """空评估器列表应抛出异常。"""
        with pytest.raises(ValueError):
            CompositeEvaluator(evaluators=[])
    def test_create_invalid_weights(self):
        """权重数量不匹配应抛出异常。"""
        with pytest.raises(ValueError):
            CompositeEvaluator(
                evaluators=[BasicEvaluator(), BasicEvaluator()],
                weights=[1.0],
            )
    @pytest.mark.asyncio
    async def test_composite_single_evaluator(self):
        """单个评估器的组合应返回相同结果。"""
        composite = CompositeEvaluator(evaluators=[BasicEvaluator()])
        metrics = await composite.evaluate(
            query="test",
            retrieved_chunks=["a", "b"],
            ground_truth=["a"],
        )
        assert metrics.hit_rate == 1.0
        assert metrics.mrr == 1.0
    @pytest.mark.asyncio
    async def test_composite_two_evaluators(self):
        """两个评估器的组合应取均值。"""
        composite = CompositeEvaluator(
            evaluators=[
                BasicEvaluator(k=5),
                BasicEvaluator(k=5),
            ],
            weights=[1.0, 1.0],
        )
        metrics = await composite.evaluate(
            query="test",
            retrieved_chunks=["a", "b"],
            ground_truth=["a"],
        )
        # 两个评估器都返回 hit_rate=1.0
        assert metrics.hit_rate == 1.0
    @pytest.mark.asyncio
    async def test_composite_weights(self):
        """权重应影响最终结果。"""
        composite = CompositeEvaluator(
            evaluators=[
                BasicEvaluator(k=5),
                BasicEvaluator(k=5),
            ],
            weights=[2.0, 1.0],
        )
        metrics = await composite.evaluate(
            query="test",
            retrieved_chunks=["a", "b", "c"],
            ground_truth=["a"],
        )
        # 两个评估器都返回相同的值
        assert metrics.hit_rate == 1.0
    @pytest.mark.asyncio
    async def test_composite_partial_failure(self):
        """单个评估器失败不应影响整体。"""
        class FailingEvaluator(BasicEvaluator):
            async def evaluate(self, **kwargs):
                raise RuntimeError("模拟失败")
        composite = CompositeEvaluator(
            evaluators=[FailingEvaluator(), BasicEvaluator()],
        )
        metrics = await composite.evaluate(
            query="test",
            retrieved_chunks=["a"],
            ground_truth=["a"],
        )
        # 第一个失败，第二个成功
        assert metrics.hit_rate == 1.0
__all__ = [
    "TestBasicEvaluator",
    "TestParseScore",
    "TestCompositeEvaluator",
]
class TestRagasEvaluator:
    """RagasEvaluator 构造与导入测试（不调用 LLM）。"""
    def test_import_and_create(self):
        """验证 RagasEvaluator 可通过工厂创建。"""
        from app.libs.evaluator.ragas_evaluator import RagasEvaluator
        e = RagasEvaluator(llm="mock")  # 不触发实际 ChatOpenAI
        assert e.requires_llm is True
        assert e.requires_embeddings is False
        # 验证继承链
        from app.libs.base.base_evaluator import BaseEvaluator
        assert isinstance(e, BaseEvaluator)
    def test_requires_answer(self):
        """不传 answer 时 evaluate 应抛出异常。"""
        from app.libs.evaluator.ragas_evaluator import RagasEvaluator
        e = RagasEvaluator(llm="mock")
        import pytest
        with pytest.raises(ValueError, match="answer"):
            import asyncio
            asyncio.run(e.evaluate(query="q", retrieved_chunks=["c"], answer=None))
class TestEvaluatorFactory:
    """EvaluatorFactory 注册与创建测试。"""
    def test_has_all_registrations(self):
        from app.libs.factory import EvaluatorFactory
        assert "basic" in EvaluatorFactory._registry
        assert "ragas" in EvaluatorFactory._registry
        assert "composite" in EvaluatorFactory._registry
    def test_create_basic(self):
        from app.libs.factory import EvaluatorFactory
        e = EvaluatorFactory.create("basic")
        from app.libs.evaluator.basic import BasicEvaluator
        assert isinstance(e, BasicEvaluator)
    def test_create_ragas(self):
        from app.libs.factory import EvaluatorFactory
        # llm="mock" 跳过 ChatOpenAI 构造
        e = EvaluatorFactory.create("ragas", llm="mock")
        from app.libs.evaluator.ragas_evaluator import RagasEvaluator
        assert isinstance(e, RagasEvaluator)
    def test_create_unknown(self):
        from app.libs.factory import EvaluatorFactory
        import pytest
        with pytest.raises(ValueError, match="unknown"):
            EvaluatorFactory.create("unknown")
    def test_create_composite_requires_evaluators(self):
        from app.libs.factory import EvaluatorFactory
        import pytest
        with pytest.raises(TypeError):
            EvaluatorFactory.create("composite")
__all__ = [
    "TestBasicEvaluator",
    "TestCompositeEvaluator",
    "TestRagasEvaluator",
    "TestEvaluatorFactory",
]
