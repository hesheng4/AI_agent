"""引用网络黄金测试 — 以受控引用图的解析解为基准

背景（第一轮审计实测发现）：
- P0-6：co_citation_analysis 与 bibliographic_coupling 语义互换
  （共引遍历 reverse_adj、耦合遍历 adjacency，两者恰好互相实现了对方）
- P0-7：bibliographic_coupling 用 reverse_adj | adjacency 并集配对，
  在"既施引又被引用"的混合图上会把施引者与参考文献混入同一集合

术语与算法（固定为断言基准）：
- 共引 co-citation：两篇文献被同一篇文献引用 -> 节点对建立在**被引文献**之间
  算法：对每篇施引文献 X，其参考文献集合 adjacency[X] 两两配对
- 文献耦合 bibliographic coupling：两篇文献共同引用同一篇文献
  -> 节点对建立在**施引文献**之间
  算法：对每篇被引文献 Z，其施引者集合 reverse_adj[Z] 两两配对
"""


from app.services.citation_network import CitationNetwork


def build(edges: list[tuple[str, str]], papers: list[str] | None = None) -> CitationNetwork:
    net = CitationNetwork()
    ids = sorted({p for e in edges for p in e} | set(papers or []))
    for pid in ids:
        net.add_paper({"id": pid, "title": f"Paper {pid}", "year": 2000})
    for citing, cited in edges:
        net.add_citation(citing, cited)
    return net


def as_pairs(items: list[dict], key: str) -> dict[tuple[str, str], int]:
    return {
        tuple(sorted((it["paper1_id"], it["paper2_id"]))): it[key] for it in items
    }


# --------------------------------------------------------------------------
# 受控图 1：施引者与被引者不重叠
#   p1 -> p3, p4 ;  p2 -> p3, p4, p5 ;  p6 -> p3
# --------------------------------------------------------------------------

EDGE_1 = [
    ("p1", "p3"),
    ("p1", "p4"),
    ("p2", "p3"),
    ("p2", "p4"),
    ("p2", "p5"),
    ("p6", "p3"),
]

# 共引：对每篇施引文献的参考文献两两配对
#   p1: {p3,p4} -> (p3,p4)+1
#   p2: {p3,p4,p5} -> (p3,p4)+1 (p3,p5)+1 (p4,p5)+1
#   p6: {p3} -> 无
EXPECTED_CO_CITATION_1 = {("p3", "p4"): 2, ("p3", "p5"): 1, ("p4", "p5"): 1}

# 耦合：对每篇被引文献的施引者两两配对
#   p3: 施引者{p1,p2,p6} -> (p1,p2)+1 (p1,p6)+1 (p2,p6)+1
#   p4: 施引者{p1,p2} -> (p1,p2)+1
#   p5: 施引者{p2} -> 无
EXPECTED_COUPLING_1 = {("p1", "p2"): 2, ("p1", "p6"): 1, ("p2", "p6"): 1}


class TestDisjointRolesGraph:
    def test_co_citation_pairs_are_cited_papers(self):
        """共引结果的节点必须是**被引**文献，且计数与解析解一致

        修复前此函数返回的是施引文献对 (p1,p2)(p1,p6)(p2,p6)——即耦合结果。
        """
        net = build(EDGE_1)
        got = as_pairs(
            net.co_citation_analysis(min_co_citations=1, top_k=50)["co_citations"],
            "co_citation_count",
        )
        assert got == EXPECTED_CO_CITATION_1

    def test_coupling_pairs_are_citing_papers(self):
        """耦合结果的节点必须是**施引**文献，且计数与解析解一致

        修复前此函数返回的是被引文献对 (p3,p4)(p3,p5)(p4,p5)——即共引结果。
        """
        net = build(EDGE_1)
        got = as_pairs(
            net.bibliographic_coupling(min_coupling=1, top_k=50)[
                "bibliographic_couplings"
            ],
            "coupling_strength",
        )
        assert got == EXPECTED_COUPLING_1

    def test_results_are_not_swapped(self):
        """两个函数的结果集合不得互换（这是 P0-6 的原始缺陷形态）"""
        net = build(EDGE_1)
        co = set(
            as_pairs(
                net.co_citation_analysis()["co_citations"], "co_citation_count"
            )
        )
        cp = set(
            as_pairs(
                net.bibliographic_coupling()["bibliographic_couplings"],
                "coupling_strength",
            )
        )
        assert co == set(EXPECTED_CO_CITATION_1)
        assert cp == set(EXPECTED_COUPLING_1)
        assert co != cp, "共引与耦合结果完全互换（P0-6 缺陷形态）"

    def test_top_k_and_threshold(self):
        net = build(EDGE_1)
        got = as_pairs(
            net.co_citation_analysis(min_co_citations=2, top_k=50)["co_citations"],
            "co_citation_count",
        )
        assert got == {("p3", "p4"): 2}

        got2 = as_pairs(
            net.bibliographic_coupling(min_coupling=2, top_k=1)[
                "bibliographic_couplings"
            ],
            "coupling_strength",
        )
        assert got2 == {("p1", "p2"): 2}


# --------------------------------------------------------------------------
# 受控图 2（混合角色）：一篇文献既施引又被引用 —— 唯一能暴露 P0-7 并集污染的形态
#   A -> C, D ;  B -> D ;  C -> D
#   A、B、C 施引；C、D 被引；C 双重角色
# --------------------------------------------------------------------------

EDGE_2 = [("A", "C"), ("A", "D"), ("B", "D"), ("C", "D")]

# 共引：施引文献的参考文献两两配对
#   A: {C,D} -> (C,D)+1 ;  B: {D} -> 无 ;  C: {D} -> 无
EXPECTED_CO_CITATION_2 = {("C", "D"): 1}

# 耦合：被引文献的施引者两两配对
#   C: 施引者{A} -> 无 ;  D: 施引者{A,B,C} -> (A,B)(A,C)(B,C) 各 +1
EXPECTED_COUPLING_2 = {("A", "B"): 1, ("A", "C"): 1, ("B", "C"): 1}


class TestMixedRolesGraph:
    def test_co_citation_excludes_citing_side(self):
        """共引不得混入施引侧节点（A、B 不应出现在共引结果中）"""
        net = build(EDGE_2)
        got = as_pairs(
            net.co_citation_analysis()["co_citations"], "co_citation_count"
        )
        assert got == EXPECTED_CO_CITATION_2
        for a, _b in got:
            assert a in ("C", "D"), f"施引侧节点 {a} 混入了共引结果"

    def test_coupling_excludes_reference_side(self):
        """耦合不得混入纯参考文献节点（D 只被引用，不应出现在耦合结果中）"""
        net = build(EDGE_2)
        got = as_pairs(
            net.bibliographic_coupling()["bibliographic_couplings"],
            "coupling_strength",
        )
        assert got == EXPECTED_COUPLING_2
        for a, b in got:
            assert a != "D" and b != "D", "纯被引节点 D 混入了耦合结果"

    def test_no_cross_role_pairs(self):
        """修复 P0-7：不得出现"施引者×参考文献"的跨界配对

        旧实现下 C 的处理集合是 reverse_adj[C]∪adjacency[C] = {A}∪{D} = {A,D}，
        会产出无意义的 (A,D) 配对（A 是施引者、D 是参考文献，二者不是
        同一类节点）。
        """
        net = build(EDGE_2)
        co = as_pairs(
            net.co_citation_analysis()["co_citations"], "co_citation_count"
        )
        cp = as_pairs(
            net.bibliographic_coupling()["bibliographic_couplings"],
            "coupling_strength",
        )
        assert ("A", "D") not in co and ("A", "D") not in cp, (
            "出现施引者×参考文献的跨界配对（P0-7 缺陷形态）"
        )


# --------------------------------------------------------------------------
# 对称性与边界
# --------------------------------------------------------------------------


class TestSymmetryAndEdges:
    def test_cocitation_and_coupling_are_duals(self):
        """在有向图上二者互为对偶：共引看入边聚合，耦合看出边聚合

        构造完全对称的图验证计数互为镜像。
        """
        edges = [("a", "c"), ("b", "c"), ("a", "d"), ("b", "d")]
        net = build(edges)
        co = as_pairs(
            net.co_citation_analysis()["co_citations"], "co_citation_count"
        )
        cp = as_pairs(
            net.bibliographic_coupling()["bibliographic_couplings"],
            "coupling_strength",
        )
        assert co == {("c", "d"): 2}
        assert cp == {("a", "b"): 2}

    def test_empty_network(self):
        net = CitationNetwork()
        co = net.co_citation_analysis()
        cp = net.bibliographic_coupling()
        assert co["n_pairs"] == 0 and co["co_citations"] == []
        assert cp["n_pairs"] == 0 and cp["bibliographic_couplings"] == []

    def test_no_self_pairs(self):
        """同一篇文献不得与自己配对"""
        net = build([("a", "b"), ("a", "c"), ("b", "b")])
        co = as_pairs(
            net.co_citation_analysis()["co_citations"], "co_citation_count"
        )
        cp = as_pairs(
            net.bibliographic_coupling()["bibliographic_couplings"],
            "coupling_strength",
        )
        for pairs in (co, cp):
            for a, b in pairs:
                assert a != b, f"出现自配对 ({a},{b})"

    def test_single_citing_paper(self):
        """单篇施引文献引多篇：只有共引有结果，耦合无结果"""
        net = build([("x", "m"), ("x", "n"), ("x", "o")])
        co = as_pairs(
            net.co_citation_analysis()["co_citations"], "co_citation_count"
        )
        assert co == {("m", "n"): 1, ("m", "o"): 1, ("n", "o"): 1}
        assert net.bibliographic_coupling()["n_pairs"] == 0
