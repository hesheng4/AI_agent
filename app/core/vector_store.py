"""向量存储 - 基于 Milvus

设计要点：
- 所有 pymilvus 同步调用通过 asyncio.to_thread 包装，避免阻塞事件循环
- 模块级实例 vector_store 通过 get_vector_store() 懒连接
- collection.load() 后用 _loaded_collections 缓存，避免重复 load
- ID 生成使用 SHA-256 截断（替代 MD5），降低碰撞概率
- 删除表达式通过 str(list) 安全构造，避免表达式注入
"""

import asyncio
import hashlib
from typing import Any

from app.config import get_settings
from app.utils.exceptions import AppException
from app.utils.logger import get_logger

logger = get_logger("vector_store")
settings = get_settings()


class VectorStoreException(AppException):
    """向量库异常"""

    def __init__(self, message: str):
        super().__init__(message, code="VECTOR_STORE_ERROR", status_code=500)


class VectorStore:
    """向量存储（Milvus）"""

    def __init__(self):
        self.host = settings.MILVUS_HOST
        self.port = settings.MILVUS_PORT
        self.client = None
        self._connected = False
        # 已 load 的集合名缓存，避免重复 load（Milvus load 是重操作）
        self._loaded_collections: set[str] = set()
        # 连接锁，防止并发首次连接；懒初始化避免跨事件循环复用
        self._connect_lock: asyncio.Lock | None = None

    async def connect(self):
        """连接 Milvus（线程安全，可重复调用）"""
        if self._connected:
            return True
        if self._connect_lock is None:
            self._connect_lock = asyncio.Lock()
        async with self._connect_lock:
            if self._connected:
                return True
            try:
                from pymilvus import connections

                # pymilvus 的 connections.connect 是同步阻塞调用
                await asyncio.to_thread(
                    connections.connect,
                    alias="default",
                    host=self.host,
                    port=self.port,
                )
                self._connected = True
                logger.info(f"Milvus连接成功: {self.host}:{self.port}")
                return True
            except ImportError:
                logger.warning("pymilvus未安装，向量检索功能不可用")
                self._connected = False
                return False
            except Exception as e:
                logger.error(f"Milvus连接失败: {e}")
                self._connected = False
                return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    async def list_collections(self) -> list[str]:
        """列出所有集合名（轻量操作，用于 health check 验证连接）

        未连接时返回空列表而非抛异常，便于 health 端点据此判断连通性。
        """
        if not self._connected:
            return []
        try:
            from pymilvus import utility

            return await asyncio.to_thread(utility.list_collections)
        except Exception as e:
            logger.warning(f"list_collections 失败: {e}")
            return []

    async def _ensure_connected(self):
        """确保已连接，未连接则尝试连接"""
        if not self._connected:
            ok = await self.connect()
            if not ok:
                raise VectorStoreException("Milvus未连接且自动连接失败")

    async def create_collection(self, collection_name: str, dimension: int = 768):
        """创建集合"""
        await self._ensure_connected()

        def _sync_create():
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema

            fields = [
                FieldSchema(
                    name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64
                ),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(
                    name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension
                ),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]

            schema = CollectionSchema(
                fields, description=f"Collection: {collection_name}"
            )
            collection = Collection(collection_name, schema)

            # 创建索引（IVF_FLAT，nlist=1024 是 Milvus 推荐的聚类中心数）
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            }
            collection.create_index("embedding", index_params)
            return collection

        try:
            await asyncio.to_thread(_sync_create)
            logger.info(f"集合创建成功: {collection_name}")
        except Exception as e:
            logger.error(f"集合创建失败: {e}")
            raise VectorStoreException(f"集合创建失败: {str(e)}")

    async def insert(
        self,
        collection_name: str,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> list[str]:
        """插入数据"""
        await self._ensure_connected()

        # 生成 ID：SHA-256 截断 32 字符（128 bit），碰撞概率远低于 MD5 16 字符
        ids = [hashlib.sha256(t.encode()).hexdigest()[:32] for t in texts]

        data = [ids, texts, embeddings]
        if metadatas:
            data.append(metadatas)
        else:
            data.append([{}] * len(texts))

        def _sync_insert():
            from pymilvus import Collection

            collection = Collection(collection_name)
            collection.insert(data)
            collection.flush()
            # 插入后 load 一次，后续 search 不再重复 load
            collection.load()
            return collection

        try:
            await asyncio.to_thread(_sync_insert)
            self._loaded_collections.add(collection_name)
            logger.info(f"插入 {len(texts)} 条数据到 {collection_name}")
            return ids
        except Exception as e:
            logger.error(f"数据插入失败: {e}")
            raise VectorStoreException(f"数据插入失败: {str(e)}")

    async def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 10,
        filter_expr: str | None = None,
    ) -> list[dict[str, Any]]:
        """向量搜索"""
        await self._ensure_connected()

        def _sync_search():
            from pymilvus import Collection

            collection = Collection(collection_name)
            # 仅在未 load 时 load（load 是重操作）
            if collection_name not in self._loaded_collections:
                collection.load()
                self._loaded_collections.add(collection_name)

            search_params = {"metric_type": "L2", "params": {"nprobe": 16}}

            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["text", "metadata"],
            )

            search_results = []
            for hits in results:
                for hit in hits:
                    search_results.append(
                        {
                            "id": hit.id,
                            "score": hit.score,
                            "text": hit.entity.get("text"),
                            "metadata": hit.entity.get("metadata"),
                        }
                    )
            return search_results

        try:
            search_results = await asyncio.to_thread(_sync_search)
            logger.info(f"搜索返回 {len(search_results)} 条结果")
            return search_results
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            raise VectorStoreException(f"向量搜索失败: {str(e)}")

    async def delete(self, collection_name: str, ids: list[str]):
        """删除数据

        安全说明：Milvus 删除表达式不支持参数化绑定，ids 通过 str(list)
        构造为合法的字符串列表字面量，恶意字符串中的引号会被 Python 的
        repr 自动转义，避免表达式注入。
        """
        await self._ensure_connected()

        safe_ids = [str(i) for i in ids if i is not None]
        if not safe_ids:
            logger.warning("删除请求的 ids 列表为空")
            return

        expr = "id in " + str(safe_ids)

        def _sync_delete():
            from pymilvus import Collection

            collection = Collection(collection_name)
            collection.delete(expr)

        try:
            await asyncio.to_thread(_sync_delete)
            logger.info(f"删除 {len(safe_ids)} 条数据")
        except Exception as e:
            logger.error(f"数据删除失败: {e}")
            raise VectorStoreException(f"数据删除失败: {str(e)}")

    async def drop_collection(self, collection_name: str):
        """删除集合"""
        await self._ensure_connected()

        def _sync_drop():
            from pymilvus import Collection, utility

            if utility.has_collection(collection_name):
                Collection(collection_name).drop()

        try:
            await asyncio.to_thread(_sync_drop)
            self._loaded_collections.discard(collection_name)
            logger.info(f"集合已删除: {collection_name}")
        except Exception as e:
            logger.error(f"集合删除失败: {e}")
            raise VectorStoreException(f"集合删除失败: {str(e)}")

    async def close(self):
        """断开连接"""
        if not self._connected:
            return
        try:
            from pymilvus import connections

            await asyncio.to_thread(connections.disconnect, "default")
        except Exception as e:
            logger.warning(f"Milvus 断开连接失败: {e}")
        finally:
            self._connected = False
            self._loaded_collections.clear()


# 全局实例
vector_store = VectorStore()


def get_vector_store() -> VectorStore:
    """获取向量存储实例（懒连接，首次使用时自动连接）"""
    return vector_store
