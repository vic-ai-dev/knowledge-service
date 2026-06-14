"""配置加载与校验单元测试。

测试范围：
  - 默认值加载
  - YAML 文件加载
  - 字段校验器（端口范围 / chunk 约束等）
  - 模型校验器（overlap < chunk_size）
  - KS_* 环境变量覆盖
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml


# ── 默认值测试 ──────────────────────────────────────────────


@pytest.mark.unit
class TestDefaults:
    """验证 Settings 默认值正确。"""

    def test_default_port_range(self, sample_settings):
        """默认端口在合法范围内。"""
        assert 1 <= sample_settings.server.port <= 65535
        assert 1 <= sample_settings.database.port <= 65535

    def test_default_database_config(self, sample_settings):
        """数据库默认配置。"""
        db = sample_settings.database
        assert db.host == "localhost"
        assert db.port == 5432
        assert db.database == "knowledge"
        assert db.max_connections >= 1

    def test_default_vector_store(self, sample_settings):
        """向量存储默认配置。"""
        vs = sample_settings.vector_store
        assert vs.backend == "pgvector"
        assert vs.database == "knowledge_rag"
        assert vs.embedding_dimensions == 1536

    def test_default_llm_config(self, sample_settings):
        """LLM 默认配置。"""
        llm = sample_settings.llm
        assert llm.provider == "openai"
        assert llm.model == "gpt-4o"

    def test_default_splitter_config(self, sample_settings):
        """分块器默认配置。"""
        sp = sample_settings.splitter
        assert sp.default.type == "recursive_character"
        assert sp.default.chunk_size >= 100
        assert sp.default.chunk_overlap < sp.default.chunk_size

    def test_default_server_config(self, sample_settings):
        """服务器默认配置。"""
        sv = sample_settings.server
        assert sv.port == 8000
        assert sv.max_file_size > 0
        assert "pdf" in sv.allowed_extensions

    def test_default_observability(self, sample_settings):
        """可观测性默认启用。"""
        obs = sample_settings.observability
        assert obs.enabled is True
        assert obs.logging.log_level == "INFO"

    def test_default_retrieval(self, sample_settings):
        """检索默认模式。"""
        ret = sample_settings.retrieval
        assert ret.rerank_backend == "cross_encoder"
        assert ret.fusion_algorithm == "rrf"


# ── 字段校验器测试 ──────────────────────────────────────────


@pytest.mark.unit
class TestFieldValidators:
    """验证字段级校验器。"""

    def test_port_too_low_raises(self):
        """端口低于 1 应报错。"""
        from app.core.settings import DatabaseConfig
        with pytest.raises(ValueError, match="port"):
            DatabaseConfig(port=0)

    def test_port_too_high_raises(self):
        """端口高于 65535 应报错。"""
        from app.core.settings import DatabaseConfig
        with pytest.raises(ValueError, match="port"):
            DatabaseConfig(port=70000)

    def test_max_connections_zero_raises(self):
        """max_connections < 1 应报错。"""
        from app.core.settings import DatabaseConfig
        with pytest.raises(ValueError, match="max_connections"):
            DatabaseConfig(max_connections=0)

    def test_chunk_size_too_small_raises(self):
        """chunk_size < 100 应报错。"""
        from app.core.settings import SplitterStrategy
        with pytest.raises(ValueError, match="chunk_size"):
            SplitterStrategy(chunk_size=50)

    def test_invalid_embedding_dims_raises(self):
        """非法 embedding 维度应报错。"""
        from app.core.settings import VectorStoreConfig
        with pytest.raises(ValueError, match="embedding_dimensions"):
            VectorStoreConfig(embedding_dimensions=256)

    def test_max_file_size_zero_raises(self):
        """max_file_size <= 0 应报错。"""
        from app.core.settings import ServerConfig
        with pytest.raises(ValueError, match="max_file_size"):
            ServerConfig(max_file_size=0)


# ── 模型校验器测试 ──────────────────────────────────────────


@pytest.mark.unit
class TestModelValidators:
    """验证跨字段模型校验器。"""

    def test_overlap_less_than_chunk(self):
        """chunk_overlap < chunk_size 正常。"""
        from app.core.settings import SplitterStrategy
        s = SplitterStrategy(chunk_size=1000, chunk_overlap=200)
        assert s.chunk_size == 1000
        assert s.chunk_overlap == 200

    def test_overlap_equal_to_chunk_raises(self):
        """chunk_overlap == chunk_size 应报错。"""
        from app.core.settings import SplitterStrategy
        with pytest.raises(ValueError, match="chunk_overlap"):
            SplitterStrategy(chunk_size=500, chunk_overlap=500)

    def test_overlap_greater_than_chunk_raises(self):
        """chunk_overlap > chunk_size 应报错。"""
        from app.core.settings import SplitterStrategy
        with pytest.raises(ValueError, match="chunk_overlap"):
            SplitterStrategy(chunk_size=300, chunk_overlap=500)


# ── YAML 加载测试 ──────────────────────────────────────────


@pytest.mark.unit
class TestYamlLoading:
    """验证 from_yaml() 加载逻辑。"""

    def test_load_from_temp_yaml(self):
        """从临时 YAML 文件加载配置。"""
        from app.core.settings import Settings

        config = {
            "server": {"port": 9000, "max_file_size": 10485760},
            "database": {"host": "test-db", "port": 6432},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            tmp_path = f.name

        try:
            settings = Settings.from_yaml(tmp_path)
            assert settings.server.port == 9000
            assert settings.server.max_file_size == 10485760
            assert settings.database.host == "test-db"
            assert settings.database.port == 6432
            # 未覆盖的字段保持默认值
            assert settings.llm.provider == "openai"
            assert settings.vector_store.embedding_dimensions == 1536
        finally:
            os.unlink(tmp_path)

    def test_load_from_nonexistent_yaml_returns_defaults(self):
        """YAML 文件不存在时返回全部默认值。"""
        from app.core.settings import Settings

        settings = Settings.from_yaml("/nonexistent/path/surely/missing.yaml")
        assert settings.server.port == 8000
        assert settings.database.port == 5432

    def test_load_from_invalid_yaml_raises_error(self):
        """非法 YAML 内容应报错。"""
        from app.core.settings import Settings

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{{{broken: yaml: }}")
            tmp_path = f.name

        try:
            with pytest.raises(yaml.YAMLError):
                Settings.from_yaml(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_yaml_overrides_partial_config(self):
        """YAML 只覆盖部分字段，其余应保持默认。"""
        from app.core.settings import Settings

        config = {"server": {"port": 8080}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            tmp_path = f.name

        try:
            settings = Settings.from_yaml(tmp_path)
            assert settings.server.port == 8080  # 覆盖
            assert settings.server.max_file_size == 52428800  # 默认
            assert settings.database.host == "localhost"  # 默认
        finally:
            os.unlink(tmp_path)


# ── 环境变量覆盖测试 ───────────────────────────────────────


@pytest.mark.unit
class TestEnvOverrides:
    """验证 KS_* 环境变量覆盖。"""

    def test_env_override_server_port(self, monkeypatch):
        """KS_SERVER__PORT 应覆盖默认端口。"""
        from app.core.settings import Settings

        monkeypatch.setenv("KS_SERVER__PORT", "3000")
        settings = Settings()
        assert settings.server.port == 3000

    def test_env_override_database_host(self, monkeypatch):
        """KS_DATABASE__HOST 应覆盖数据库主机。"""
        from app.core.settings import Settings

        monkeypatch.setenv("KS_DATABASE__HOST", "pg-prod.example.com")
        settings = Settings()
        assert settings.database.host == "pg-prod.example.com"

    def test_env_override_llm_provider(self, monkeypatch):
        """KS_LLM__PROVIDER 应覆盖 LLM 提供商。"""
        from app.core.settings import Settings

        monkeypatch.setenv("KS_LLM__PROVIDER", "openai")
        settings = Settings()
        assert settings.llm.provider == "openai"


# ── 服务单例测试 ────────────────────────────────────────────


@pytest.mark.unit
class TestSettingsSingleton:
    """验证 get_settings() 单例行为。"""

    def test_get_settings_returns_same_instance(self):
        """多次调用应返回同一个实例。"""
        import app.core.settings as s
        s._settings = None
        s1 = s.get_settings()
        s2 = s.get_settings()
        assert s1 is s2


# ── 合法边界值测试 ──────────────────────────────────────────


@pytest.mark.unit
class TestEdgeCases:
    """验证合法边界值。"""

    def test_port_minimum(self):
        """端口 = 1 应合法。"""
        from app.core.settings import DatabaseConfig
        cfg = DatabaseConfig(port=1)
        assert cfg.port == 1

    def test_port_maximum(self):
        """端口 = 65535 应合法。"""
        from app.core.settings import DatabaseConfig
        cfg = DatabaseConfig(port=65535)
        assert cfg.port == 65535

    def test_chunk_size_minimum(self):
        """chunk_size = 100 应合法。"""
        from app.core.settings import SplitterStrategy
        cfg = SplitterStrategy(chunk_size=100, chunk_overlap=0)
        assert cfg.chunk_size == 100

    def test_max_connections_minimum(self):
        """max_connections = 1 应合法。"""
        from app.core.settings import DatabaseConfig
        cfg = DatabaseConfig(max_connections=1)
        assert cfg.max_connections == 1

    def test_all_valid_embedding_dims(self):
        """所有合法的 embedding 维度都应通过。"""
        from app.core.settings import VectorStoreConfig
        for dim in (384, 512, 768, 1024, 1536, 3072):
            cfg = VectorStoreConfig(embedding_dimensions=dim)
            assert cfg.embedding_dimensions == dim
