"""MCP SSE 服务器 — FastMCP 集成。

使用 FastMCP SSE Transport 模式，挂载到 FastAPI 应用路径：
  http://localhost:8000/mcp/sse

工具列表：
  - query_knowledge_hub：查询知识库
  - get_document_summary：获取文档摘要
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from app.common.log import get_logger
from app.common.enums import SearchMode

logger = get_logger(__name__)

# ── 创建 FastMCP 实例 ──────────────────────────────────

mcp = FastMCP(
    "Knowledge Service",
    instructions=(
        "RAG 知识服务平台 MCP 接口。"
        "支持知识库查询、集合浏览、文档摘要获取。"
    ),
    debug=False,
)

# ── 工具注册 ───────────────────────────────────────────

@mcp.tool(
    name="query_knowledge_hub",
    description="查询知识库，返回 Top-K 相关文档片段及引用。",
)
async def query_knowledge_hub(
    query: str,
    top_k: int = 5,
    search_mode: str = SearchMode.HYBRID.value,
    rerank: bool = True,
) -> str:
    """查询知识库。

    Args:
        query: 查询文本。
        top_k: 返回的最大结果数（默认 5）。
        search_mode: 检索模式，hybrid（混合）或 vector_only（仅向量）。
        rerank: 是否启用重排序（默认启用）。

    Returns:
        格式化的检索结果文本。
    """
    # TODO(E11): 连接 QueryPipeline 实现真实检索
    logger.info(
        "mcp_query",
        message="MCP 查询请求",
        metadata={"query": query, "top_k": top_k, "search_mode": search_mode, "rerank": rerank},
    )
    return f"知识库查询: {query}\n(TODO: 实际检索实现)"

@mcp.tool(
    name="list_collections",
    description="列出知识库中所有可用的集合/分类。",
)
async def list_collections() -> str:
    """列出知识库集合与分类。"""
    # TODO(E11): 连接 Database 查询实际集合
    logger.info("mcp_list_collections", message="MCP 列出集合")
    return "可用集合: default\n分类: employee_handbook, compliance, technical_spec, architecture\n语言: zh, en"

@mcp.tool(
    name="get_document_summary",
    description="获取指定文档的摘要信息（标题、类型、大小、分块数等）。",
)
async def get_document_summary(doc_id: str) -> str:
    """获取文档摘要。

    Args:
        doc_id: 文档 ID。

    Returns:
        文档摘要文本。
    """
    # TODO(E11): 连接 Database 查询实际文档摘要
    logger.info(
        "mcp_doc_summary",
        message="MCP 文档摘要请求",
        metadata={"doc_id": doc_id},
    )
    return f"文档 {doc_id} 摘要\n(TODO: 实际文档查询实现)"

# ── SSE App ────────────────────────────────────────────

def create_mcp_sse_app() -> Starlette:
    """创建 MCP SSE Transport Starlette ASGI 应用。

    用法（在 main.py 中挂载）:
        app.mount("/mcp", create_mcp_sse_app())
    """
    return mcp.sse_app()

__all__ = [
    "mcp",
    "create_mcp_sse_app",
    "query_knowledge_hub",
    "get_document_summary",
]
