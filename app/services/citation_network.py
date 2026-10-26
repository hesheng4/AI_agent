"""引用网络分析服务 - 引用关系图、共被引分析、研究脉络发现"""

from collections import defaultdict
from typing import Any

from app.utils.logger import get_logger

logger = get_logger("services.citation_network")


class CitationNetwork:
    """引用网络分析器"""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}  # paper_id -> node info
        self.edges: list[dict[str, Any]] = []  # citation edges
        self.adjacency: dict[str, set[str]] = defaultdict(
            set
        )  # directed: paper_id -> {cited_ids}
        self.reverse_adj: dict[str, set[str]] = defaultdict(
            set
        )  # cited_by: paper_id -> {citing_ids}

    def add_paper(self, paper: dict[str, Any]) -> None:
        """添加论文节点"""
        pid = paper.get("id", paper.get("paper_id", ""))
        if not pid:
            return
        self.nodes[pid] = {
            "id": pid,
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "year": paper.get("year"),
            "journal": paper.get("journal", ""),
            "citation_count": paper.get("citation_count", 0),
            "abstract": paper.get("abstract", ""),
            "source": paper.get("source", ""),
        }

    def add_papers_batch(self, papers: list[dict[str, Any]]) -> None:
        """批量添加论文节点"""
        for p in papers:
            self.add_paper(p)

    def add_citation(self, citing_id: str, cited_id: str, weight: float = 1.0) -> None:
        """添加引用关系 (citing -> cited，即 citing 引用了 cited)"""
        if citing_id not in self.nodes:
            self.nodes[citing_id] = {"id": citing_id, "title": citing_id}
        if cited_id not in self.nodes:
            self.nodes[cited_id] = {"id": cited_id, "title": cited_id}

        self.edges.append({"source": citing_id, "target": cited_id, "weight": weight})
        self.adjacency[citing_id].add(cited_id)
        self.reverse_adj[cited_id].add(citing_id)

    def add_citations_batch(self, citations: list[dict[str, Any]]) -> None:
        """批量添加引用关系

        Args:
            citations: [{"citing": "id1", "cited": "id2"}, ...]
        """
        for c in citations:
            self.add_citation(
                c.get("citing", c.get("source", "")),
                c.get("cited", c.get("target", "")),
                c.get("weight", 1.0),
            )

    def build_from_references(self, papers_with_refs: list[dict[str, Any]]) -> None:
        """从论文及其引用列表构建网络

        Args:
            papers_with_refs: [{"id": ..., "references": ["id1", "id2", ...]}, ...]
        """
        for paper in papers_with_refs:
            self.add_paper(paper)
            pid = paper.get("id", paper.get("paper_id", ""))
            refs = paper.get("references", [])
            for ref_id in refs:
                self.add_citation(pid, ref_id)

    # ========== 网络指标 ==========

    def compute_metrics(self) -> dict[str, Any]:
        """计算网络整体指标"""
        n_nodes = len(self.nodes)
        n_edges = len(self.edges)

        # 密度
        max_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
        density = n_edges / max_edges if max_edges > 0 else 0

        # 度分布
        in_degrees = defaultdict(int)
        out_degrees = defaultdict(int)
        for citing_id in self.adjacency:
            out_degrees[citing_id] = len(self.adjacency[citing_id])
        for cited_id in self.reverse_adj:
            in_degrees[cited_id] = len(self.reverse_adj[cited_id])

        # 平均度
        avg_in_degree = sum(in_degrees.values()) / n_nodes if n_nodes > 0 else 0
        avg_out_degree = sum(out_degrees.values()) / n_nodes if n_nodes > 0 else 0

        # 连通分量
        components = self._find_weakly_connected_components()
        largest_component_size = max(len(c) for c in components) if components else 0

        # 入度Top论文（被引最多）
        top_cited = sorted(
            [(pid, len(self.reverse_adj.get(pid, set()))) for pid in self.nodes],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # 出度Top论文（引用最多）
        top_citing = sorted(
            [(pid, len(self.adjacency.get(pid, set()))) for pid in self.nodes],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "density": round(density, 6),
            "avg_in_degree": round(avg_in_degree, 4),
            "avg_out_degree": round(avg_out_degree, 4),
            "n_components": len(components),
            "largest_component_size": largest_component_size,
            "top_cited_papers": [
                {"id": pid, "title": self.nodes[pid].get("title", ""), "in_degree": deg}
                for pid, deg in top_cited
                if deg > 0
            ],
            "top_citing_papers": [
                {
                    "id": pid,
                    "title": self.nodes[pid].get("title", ""),
                    "out_degree": deg,
                }
                for pid, deg in top_citing
                if deg > 0
            ],
        }

    def page_rank(
        self, alpha: float = 0.85, max_iter: int = 100, tol: float = 1e-6
    ) -> dict[str, float]:
        """PageRank计算 - 识别高影响力论文"""
        n = len(self.nodes)
        if n == 0:
            return {}

        node_ids = list(self.nodes.keys())
        {pid: i for i, pid in enumerate(node_ids)}

        # 初始化
        pr = {pid: 1.0 / n for pid in node_ids}

        for iteration in range(max_iter):
            new_pr = {}
            for pid in node_ids:
                # 来自入边的贡献
                rank_sum = 0.0
                for citing_id in self.reverse_adj.get(pid, set()):
                    out_deg = len(self.adjacency.get(citing_id, set()))
                    if out_deg > 0:
                        rank_sum += pr[citing_id] / out_deg

                new_pr[pid] = (1 - alpha) / n + alpha * rank_sum

            # 检查收敛
            diff = sum(abs(new_pr[pid] - pr[pid]) for pid in node_ids)
            pr = new_pr
            if diff < tol:
                break

        return {pid: round(score, 6) for pid, score in pr.items()}

    def get_influential_papers(self, top_k: int = 10) -> list[dict[str, Any]]:
        """获取高影响力论文（基于PageRank）"""
        pr = self.page_rank()
        sorted_papers = sorted(pr.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [
            {
                "id": pid,
                "title": self.nodes[pid].get("title", ""),
                "authors": self.nodes[pid].get("authors", []),
                "year": self.nodes[pid].get("year"),
                "journal": self.nodes[pid].get("journal", ""),
                "page_rank": score,
                "in_degree": len(self.reverse_adj.get(pid, set())),
                "out_degree": len(self.adjacency.get(pid, set())),
            }
            for pid, score in sorted_papers
        ]

    # ========== 引用关系图 ==========

    def get_citation_graph(self, paper_id: str, depth: int = 2) -> dict[str, Any]:
        """获取某篇论文的引用关系图（BFS展开）

        Args:
            paper_id: 起始论文ID
            depth: 展开深度
        """
        nodes = []
        edges = []
        visited = set()

        def bfs(current_id: str, current_depth: int) -> None:
            if current_depth > depth or current_id in visited:
                return
            visited.add(current_id)

            node = self.nodes.get(current_id, {"id": current_id, "title": current_id})
            nodes.append(
                {
                    "id": current_id,
                    "title": node.get("title", ""),
                    "authors": node.get("authors", []),
                    "year": node.get("year"),
                    "citation_count": node.get("citation_count", 0),
                    "depth": current_depth,
                }
            )

            # 引用的论文（出边）
            for cited_id in self.adjacency.get(current_id, set()):
                edges.append(
                    {"source": current_id, "target": cited_id, "type": "cites"}
                )
                bfs(cited_id, current_depth + 1)

            # 被引的论文（入边）
            for citing_id in self.reverse_adj.get(current_id, set()):
                edges.append(
                    {"source": citing_id, "target": current_id, "type": "cites"}
                )
                bfs(citing_id, current_depth + 1)

        bfs(paper_id, 0)

        return {
            "center_paper": paper_id,
            "depth": depth,
            "nodes": nodes,
            "edges": edges,
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "chart_config": {
                "chart_type": "citation_network",
                "title": (
                    f"引用关系图: "
                    f"{self.nodes.get(paper_id, {}).get('title', paper_id)[:30]}"
                ),
                "nodes": nodes,
                "edges": edges,
            },
        }

    def get_citation_tree(
        self, paper_id: str, direction: str = "forward", max_depth: int = 3
    ) -> dict[str, Any]:
        """获取引用树（前向=被引，后向=引用）

        Args:
            direction: "forward" (被谁引用) 或 "backward" (引用了谁)
        """
        tree = {
            "id": paper_id,
            "title": self.nodes.get(paper_id, {}).get("title", ""),
            "children": [],
        }

        def build_tree(
            node_id: str, current_depth: int, tree_node: dict[str, Any]
        ) -> None:
            if current_depth >= max_depth:
                return

            if direction == "forward":
                # 被引：谁引用了这篇论文
                next_ids = self.reverse_adj.get(node_id, set())
            else:
                # 引用：这篇论文引用了谁
                next_ids = self.adjacency.get(node_id, set())

            for nid in next_ids:
                child = {
                    "id": nid,
                    "title": self.nodes.get(nid, {}).get("title", ""),
                    "year": self.nodes.get(nid, {}).get("year"),
                    "children": [],
                }
                tree_node["children"].append(child)
                build_tree(nid, current_depth + 1, child)

        build_tree(paper_id, 0, tree)
        return tree

    # ========== 共被引分析 ==========

    def co_citation_analysis(
        self, min_co_citations: int = 1, top_k: int = 50
    ) -> dict[str, Any]:
        """共被引分析 - 两篇论文同时被引用的频率

        如果论文A和B经常被同一篇论文引用，说明它们在研究主题上密切相关。

        算法：对每篇施引文献 X，把 X 的参考文献集合 adjacency[X] 中的
        文献两两配对。得到的节点对是**被引文献**之间的关系。

        修复说明（P0-6）：此前遍历的是 reverse_adj（被引 -> 施引集合），
        对被引文献的施引者两两配对，算出的实际是文献耦合，与本函数语义
        正好相反。
        """
        co_citation_counts: dict[tuple[str, str], int] = defaultdict(int)

        # 遍历每篇施引文献，统计其参考文献两两组成的共被引对
        for citing_id in self.adjacency:
            cited_ids = sorted(self.adjacency[citing_id])
            # 对于每对被引论文
            for i in range(len(cited_ids)):
                for j in range(i + 1, len(cited_ids)):
                    pair = (cited_ids[i], cited_ids[j])
                    co_citation_counts[pair] += 1

        # 筛选和排序
        co_citations = [
            {
                "paper1_id": p1,
                "paper1_title": self.nodes.get(p1, {}).get("title", ""),
                "paper2_id": p2,
                "paper2_title": self.nodes.get(p2, {}).get("title", ""),
                "co_citation_count": count,
            }
            for (p1, p2), count in co_citation_counts.items()
            if count >= min_co_citations
        ]
        co_citations.sort(key=lambda x: x["co_citation_count"], reverse=True)
        co_citations = co_citations[:top_k]

        # 构建共被引网络（用于可视化）
        co_cite_nodes = set()
        co_cite_edges = []
        for cc in co_citations:
            co_cite_nodes.add(cc["paper1_id"])
            co_cite_nodes.add(cc["paper2_id"])
            co_cite_edges.append(
                {
                    "source": cc["paper1_id"],
                    "target": cc["paper2_id"],
                    "weight": cc["co_citation_count"],
                }
            )

        return {
            "co_citations": co_citations,
            "n_pairs": len(co_citations),
            "n_unique_papers": len(co_cite_nodes),
            "network": {
                "nodes": [
                    {
                        "id": pid,
                        "title": self.nodes.get(pid, {}).get("title", ""),
                        "year": self.nodes.get(pid, {}).get("year"),
                        "citation_count": len(self.reverse_adj.get(pid, set())),
                    }
                    for pid in co_cite_nodes
                ],
                "edges": co_cite_edges,
            },
            "chart_config": {"chart_type": "co_citation", "title": "共被引分析网络"},
        }

    def bibliographic_coupling(
        self, min_coupling: int = 1, top_k: int = 50
    ) -> dict[str, Any]:
        """文献耦合分析 - 两篇论文引用相同文献的数量

        如果论文A和B引用了大量相同的参考文献，说明它们研究主题相近。

        算法：对每篇被引文献 Z，把引用 Z 的施引文献集合 reverse_adj[Z]
        两两配对。得到的节点对是**施引文献**之间的关系。

        修复说明（P0-6/P0-7）：此前遍历 adjacency（施引 -> 被引集合），
        算出的实际是共被引，与本函数语义相反；且把 reverse_adj[cited] 与
        adjacency[cited] 取并集，在一般引用图上（一篇文献通常既施引又被
        引用）会把"引用它的"与"它引用的"混入同一集合，产出无意义配对。
        """
        coupling_counts: dict[tuple[str, str], int] = defaultdict(int)

        # 遍历每篇被引文献，统计引用它的施引文献两两组成的耦合对
        for cited_id in self.reverse_adj:
            citing_ids = sorted(self.reverse_adj[cited_id])
            for i in range(len(citing_ids)):
                for j in range(i + 1, len(citing_ids)):
                    pair = (citing_ids[i], citing_ids[j])
                    coupling_counts[pair] += 1

        # 筛选和排序
        couplings = [
            {
                "paper1_id": p1,
                "paper1_title": self.nodes.get(p1, {}).get("title", ""),
                "paper2_id": p2,
                "paper2_title": self.nodes.get(p2, {}).get("title", ""),
                "coupling_strength": count,
            }
            for (p1, p2), count in coupling_counts.items()
            if count >= min_coupling
        ]
        couplings.sort(key=lambda x: x["coupling_strength"], reverse=True)
        couplings = couplings[:top_k]

        return {
            "bibliographic_couplings": couplings,
            "n_pairs": len(couplings),
            "chart_config": {"chart_type": "co_citation", "title": "文献耦合分析网络"},
        }

    # ========== 研究脉络发现 ==========

    def research_lineage(self, paper_id: str, max_depth: int = 5) -> dict[str, Any]:
        """追溯研究脉络 - 从一篇论文回溯到其学术根源

        通过引用链追溯，发现研究的演化路径。
        """
        lineage = []
        visited = set()

        def trace_back(current_id: str, depth: int) -> None:
            if depth >= max_depth or current_id in visited:
                return
            visited.add(current_id)

            # 获取该论文引用的论文
            cited_ids = list(self.adjacency.get(current_id, set()))
            if not cited_ids:
                return

            node = self.nodes.get(current_id, {"id": current_id, "title": current_id})
            step = {
                "depth": depth,
                "paper_id": current_id,
                "title": node.get("title", ""),
                "year": node.get("year"),
                "n_references": len(cited_ids),
                "key_references": [],
            }

            # 按被引次数排序，选取最重要的引用
            cited_sorted = sorted(
                cited_ids,
                key=lambda x: len(self.reverse_adj.get(x, set())),
                reverse=True,
            )[:3]

            for ref_id in cited_sorted:
                ref_node = self.nodes.get(ref_id, {"id": ref_id, "title": ref_id})
                step["key_references"].append(
                    {
                        "id": ref_id,
                        "title": ref_node.get("title", ""),
                        "year": ref_node.get("year"),
                        "citation_count": len(self.reverse_adj.get(ref_id, set())),
                    }
                )

            lineage.append(step)

            # 继续追溯最重要的引用
            if cited_sorted:
                trace_back(cited_sorted[0], depth + 1)

        trace_back(paper_id, 0)

        return {
            "origin_paper": paper_id,
            "lineage": lineage,
            "depth_traced": len(lineage),
            "research_evolution": self._extract_evolution_themes(lineage),
        }

    def research_frontier(
        self, year_from: int = 2020, top_k: int = 20
    ) -> dict[str, Any]:
        """识别研究前沿 - 近年高影响力论文

        通过PageRank和年份筛选，识别最新研究热点。
        """
        pr = self.page_rank()

        # 筛选近年论文
        recent_papers = []
        for pid, score in pr.items():
            node = self.nodes.get(pid, {})
            year = node.get("year")
            if year and year >= year_from:
                recent_papers.append(
                    {
                        "id": pid,
                        "title": node.get("title", ""),
                        "authors": node.get("authors", []),
                        "year": year,
                        "journal": node.get("journal", ""),
                        "page_rank": score,
                        "in_degree": len(self.reverse_adj.get(pid, set())),
                        "out_degree": len(self.adjacency.get(pid, set())),
                    }
                )

        recent_papers.sort(key=lambda x: x["page_rank"], reverse=True)
        recent_papers = recent_papers[:top_k]

        # 识别新兴主题（基于共被引聚类）
        emerging_clusters = self._detect_clusters(recent_papers)

        return {
            "year_from": year_from,
            "frontier_papers": recent_papers,
            "n_papers": len(recent_papers),
            "emerging_clusters": emerging_clusters,
        }

    def knowledge_diffusion(self, paper_id: str, max_depth: int = 3) -> dict[str, Any]:
        """知识扩散分析 - 追踪一篇论文的影响力传播路径"""
        diffusion_paths = []
        visited = set()

        def trace_forward(current_id: str, depth: int, path: list[str]) -> None:
            if depth >= max_depth or current_id in visited:
                return
            visited.add(current_id)

            citing_ids = list(self.reverse_adj.get(current_id, set()))
            if not citing_ids:
                return

            # 按被引次数排序
            citing_sorted = sorted(
                citing_ids,
                key=lambda x: len(self.reverse_adj.get(x, set())),
                reverse=True,
            )[:5]

            node = self.nodes.get(current_id, {"id": current_id, "title": current_id})
            step = {
                "depth": depth,
                "paper_id": current_id,
                "title": node.get("title", ""),
                "year": node.get("year"),
                "citing_papers": [
                    {
                        "id": cid,
                        "title": self.nodes.get(cid, {}).get("title", ""),
                        "year": self.nodes.get(cid, {}).get("year"),
                    }
                    for cid in citing_sorted
                ],
            }
            diffusion_paths.append(step)

            for cid in citing_sorted[:2]:  # 每层最多追踪2条
                trace_forward(cid, depth + 1, path + [cid])

        trace_forward(paper_id, 0, [])

        return {
            "origin_paper": paper_id,
            "diffusion_paths": diffusion_paths,
            "total_reached": len(visited),
        }

    # ========== 时间线分析 ==========

    def citation_timeline(self, paper_id: str) -> dict[str, Any]:
        """引用时间线 - 按年份统计被引趋势"""
        citing_papers = self.reverse_adj.get(paper_id, set())

        year_counts: dict[int, int] = defaultdict(int)
        for citing_id in citing_papers:
            year = self.nodes.get(citing_id, {}).get("year")
            if year:
                year_counts[year] += 1

        timeline = sorted(
            [{"year": y, "count": c} for y, c in year_counts.items()],
            key=lambda x: x["year"],
        )

        # 累计引用
        cumulative = 0
        for item in timeline:
            cumulative += item["count"]
            item["cumulative"] = cumulative

        return {
            "paper_id": paper_id,
            "title": self.nodes.get(paper_id, {}).get("title", ""),
            "total_citations": len(citing_papers),
            "timeline": timeline,
            "chart_config": {
                "chart_type": "trend",
                "year": "year",
                "count": "count",
                "title": (
                    f"引用趋势: {self.nodes.get(paper_id, {}).get('title', '')[:30]}"
                ),
                "xlabel": "年份",
                "ylabel": "被引次数",
            },
        }

    def field_evolution(self, bin_years: int = 5) -> dict[str, Any]:
        """领域演化分析 - 按时间段统计论文发表趋势"""
        year_counts: dict[int, int] = defaultdict(int)

        for pid, node in self.nodes.items():
            year = node.get("year")
            if year:
                # 按bin_years分组
                binned = (year // bin_years) * bin_years
                year_counts[binned] += 1

        evolution = sorted(
            [
                {"period": f"{y}-{y + bin_years - 1}", "start_year": y, "count": c}
                for y, c in year_counts.items()
            ],
            key=lambda x: x["start_year"],
        )

        return {
            "bin_years": bin_years,
            "evolution": evolution,
            "chart_config": {
                "chart_type": "bar",
                "x": "period",
                "y": "count",
                "title": "领域论文发表趋势",
                "xlabel": "时间段",
                "ylabel": "论文数量",
            },
        }

    # ========== 聚类与主题发现 ==========

    def detect_research_clusters(
        self, algorithm: str = "louvain", min_cluster_size: int = 3
    ) -> dict[str, Any]:
        """检测研究聚类/社区"""
        if algorithm == "louvain":
            return self._louvain_clustering(min_cluster_size)
        else:
            return self._simple_clustering(min_cluster_size)

    def _louvain_clustering(self, min_cluster_size: int) -> dict[str, Any]:
        """简化版Louvain社区检测"""
        # 构建无向图（基于共被引）
        undirected_adj: dict[str, set[str]] = defaultdict(set)
        for citing_id in self.adjacency:
            for cited_id in self.adjacency[citing_id]:
                undirected_adj[citing_id].add(cited_id)
                undirected_adj[cited_id].add(citing_id)

        # 初始化：每个节点一个社区
        community = {pid: i for i, pid in enumerate(self.nodes)}
        improved = True
        iteration = 0

        while improved and iteration < 50:
            improved = False
            iteration += 1

            for pid in self.nodes:
                if pid not in undirected_adj:
                    continue

                current_comm = community[pid]
                neighbor_comms: defaultdict[int, int] = defaultdict(int)
                for neighbor in undirected_adj[pid]:
                    neighbor_comms[community[neighbor]] += 1

                if not neighbor_comms:
                    continue

                best_comm = max(neighbor_comms, key=neighbor_comms.get)
                if best_comm != current_comm:
                    community[pid] = best_comm
                    improved = True

        # 整理聚类结果
        clusters: dict[int, list[str]] = defaultdict(list)
        for pid, comm in community.items():
            clusters[comm].append(pid)

        # 过滤小聚类
        clusters = {k: v for k, v in clusters.items() if len(v) >= min_cluster_size}

        result_clusters: list[dict[str, Any]] = []
        for comm_id, members in clusters.items():
            # 提取聚类特征
            titles = [self.nodes.get(pid, {}).get("title", "") for pid in members[:5]]
            years: list[Any] = [
                self.nodes.get(pid, {}).get("year")
                for pid in members
                if self.nodes.get(pid, {}).get("year")
            ]

            result_clusters.append(
                {
                    "cluster_id": comm_id,
                    "size": len(members),
                    "papers": [
                        {
                            "id": pid,
                            "title": self.nodes.get(pid, {}).get("title", ""),
                            "year": self.nodes.get(pid, {}).get("year"),
                        }
                        for pid in members[:10]
                    ],
                    "sample_titles": titles,
                    "year_range": [min(years), max(years)] if years else None,
                }
            )

        result_clusters.sort(key=lambda x: x["size"], reverse=True)

        return {
            "algorithm": "louvain",
            "n_clusters": len(result_clusters),
            "clusters": result_clusters,
            "modularity": self._compute_modularity(community, undirected_adj),
        }

    def _simple_clustering(self, min_cluster_size: int) -> dict[str, Any]:
        """简单聚类 - 基于共被引关系"""
        co_cite = self.co_citation_analysis(min_co_citations=2, top_k=200)

        # 使用union-find
        parent = {pid: pid for pid in self.nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # 根据共被引关系合并
        for cc in co_cite["co_citations"]:
            union(cc["paper1_id"], cc["paper2_id"])

        # 收集聚类
        clusters: dict[str, list[str]] = defaultdict(list)
        for pid in self.nodes:
            root = find(pid)
            clusters[root].append(pid)

        clusters = {k: v for k, v in clusters.items() if len(v) >= min_cluster_size}

        result: list[dict[str, Any]] = []
        for i, (root, members) in enumerate(clusters.items()):
            result.append(
                {
                    "cluster_id": i,
                    "size": len(members),
                    "papers": [
                        {
                            "id": pid,
                            "title": self.nodes.get(pid, {}).get("title", ""),
                            "year": self.nodes.get(pid, {}).get("year"),
                        }
                        for pid in members[:10]
                    ],
                }
            )

        result.sort(key=lambda x: x["size"], reverse=True)

        return {
            "algorithm": "co_citation_union_find",
            "n_clusters": len(result),
            "clusters": result,
        }

    # ========== 辅助方法 ==========

    def _find_weakly_connected_components(self) -> list[set[str]]:
        """查找弱连通分量"""
        undirected: dict[str, set[str]] = defaultdict(set)
        for citing_id in self.adjacency:
            for cited_id in self.adjacency[citing_id]:
                undirected[citing_id].add(cited_id)
                undirected[cited_id].add(citing_id)

        visited = set()
        components = []

        for pid in self.nodes:
            if pid in visited:
                continue
            component = set()
            stack = [pid]
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)
                stack.extend(undirected.get(node, set()) - visited)
            components.append(component)

        return components

    def _compute_modularity(
        self, community: dict[str, int], adj: dict[str, set[str]]
    ) -> float:
        """计算模块度"""
        m = sum(len(neighbors) for neighbors in adj.values()) / 2
        if m == 0:
            return 0.0

        q = 0.0
        for pid in self.nodes:
            for neighbor in adj.get(pid, set()):
                if community[pid] == community[neighbor]:
                    k_i = len(adj.get(pid, set()))
                    k_j = len(adj.get(neighbor, set()))
                    q += 1 - k_i * k_j / (2 * m)

        return round(q / (2 * m), 6)

    def _extract_evolution_themes(
        self, lineage: list[dict[str, Any]]
    ) -> list[str]:
        """从研究脉络中提取演化主题"""
        themes = []
        for step in lineage:
            refs = step.get("key_references", [])
            if refs:
                # 简单提取标题关键词
                titles = " ".join(r.get("title", "") for r in refs)
                words = [w for w in titles.split() if len(w) > 4]
                if words:
                    from collections import Counter

                    top_word = Counter(words).most_common(1)[0][0]
                    themes.append(top_word)
        return themes

    def _detect_clusters(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """简单主题聚类检测"""
        if not papers:
            return []

        # 按期刊分组
        journal_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for p in papers:
            journal = p.get("journal", "unknown")
            journal_groups[journal].append(p)

        clusters = []
        for journal, group in journal_groups.items():
            if len(group) >= 2:
                clusters.append(
                    {
                        "theme": journal,
                        "n_papers": len(group),
                        "avg_page_rank": round(
                            sum(p["page_rank"] for p in group) / len(group), 6
                        ),
                        "papers": [
                            {"id": p["id"], "title": p["title"]} for p in group[:5]
                        ],
                    }
                )

        clusters.sort(key=lambda x: x["avg_page_rank"], reverse=True)
        return clusters

    # ========== 导出 ==========

    def to_graph_data(self) -> dict[str, Any]:
        """导出为图数据（用于可视化）"""
        return {
            "nodes": [
                {
                    "id": pid,
                    "title": node.get("title", ""),
                    "year": node.get("year"),
                    "citation_count": len(self.reverse_adj.get(pid, set())),
                    "authors": node.get("authors", []),
                }
                for pid, node in self.nodes.items()
            ],
            "edges": self.edges,
        }

    def to_adjacency_matrix(self) -> dict[str, Any]:
        """导出邻接矩阵"""
        node_ids = sorted(self.nodes.keys())
        n = len(node_ids)
        node_idx = {pid: i for i, pid in enumerate(node_ids)}

        matrix = [[0] * n for _ in range(n)]
        for citing_id in self.adjacency:
            for cited_id in self.adjacency[citing_id]:
                if citing_id in node_idx and cited_id in node_idx:
                    matrix[node_idx[citing_id]][node_idx[cited_id]] = 1

        return {
            "node_ids": node_ids,
            "node_labels": [
                self.nodes.get(pid, {}).get("title", pid)[:30] for pid in node_ids
            ],
            "matrix": matrix,
            "n": n,
        }
