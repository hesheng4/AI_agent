"""引用网络实测：构造已知答案的小型引用图，对照图论解析解"""

import sys

sys.path.insert(0, ".")

from app.services.citation_network import CitationNetwork

# 受控引用图（citing -> cited）：
#   p1 -> p3, p4
#   p2 -> p3, p4, p5
#   p6 -> p3
#
# 共引（被同一篇文献同时引用）：
#   (p3,p4): 被 p1、p2 共引 -> 2
#   (p3,p5): 被 p2 共引     -> 1
#   (p4,p5): 被 p2 共引     -> 1
# 文献耦合（共同引用同一篇文献）：
#   (p1,p2): 共同引用 p3、p4 -> 2
#   (p1,p6): 共同引用 p3     -> 1
#   (p2,p6): 共同引用 p3     -> 1

EDGES = [("p1", "p3"), ("p1", "p4"), ("p2", "p3"), ("p2", "p4"), ("p2", "p5"), ("p6", "p3")]

EXPECTED_COCITATION = {("p3", "p4"): 2, ("p3", "p5"): 1, ("p4", "p5"): 1}
EXPECTED_COUPLING = {("p1", "p2"): 2, ("p1", "p6"): 1, ("p2", "p6"): 1}


def build():
    net = CitationNetwork()
    for pid in ("p1", "p2", "p3", "p4", "p5", "p6"):
        net.add_paper({"id": pid, "title": f"Paper {pid}", "year": 2000 + int(pid[1])})
    for a, b in EDGES:
        net.add_citation(a, b)
    return net


def norm(pair):
    return tuple(sorted(pair))


print("=" * 78)
print("引用网络实测审计 — app/services/citation_network.py")
print("=" * 78)

net = build()

# ---------------- 共引 ----------------
print("\n[1] co_citation_analysis：与解析解对照")
try:
    r = net.co_citation_analysis(min_co_citations=1, top_k=50)
    pairs = r.get("pairs") or r.get("co_citations") or r.get("results") or []
    print(f"    返回顶层键: {list(r.keys())}")
    got = {}
    for item in pairs:
        if isinstance(item, dict):
            a = item.get("paper1_id") or item.get("paper_a") or item.get("source")
            b = item.get("paper2_id") or item.get("paper_b") or item.get("target")
            c = (
                item.get("co_citation_count")
                or item.get("count")
                or item.get("strength")
                or item.get("weight")
            )
            if a and b:
                got[norm((a, b))] = c
    print(f"    解析得到 {len(got)} 对，期望 {len(EXPECTED_COCITATION)} 对")
    ok = True
    for k, v in sorted(EXPECTED_COCITATION.items()):
        g = got.get(norm(k))
        flag = "ok" if g == v else f"✗ 期望 {v}"
        if g != v:
            ok = False
        print(f"    {k}: 实得 {g}  {flag}")
    extra = set(got) - {norm(k) for k in EXPECTED_COCITATION}
    if extra:
        print(f"    ⚠ 多出未预期项: {sorted(extra)}")
    print(f"    → {'PASS' if ok and not extra else 'FAIL'}")
except Exception as e:
    print(f"    ✗ 抛出异常: {type(e).__name__}: {e}")

# ---------------- 耦合 ----------------
print("\n[2] bibliographic_coupling：与解析解对照")
try:
    r = net.bibliographic_coupling(min_coupling=1, top_k=50)
    pairs = (
        r.get("pairs")
        or r.get("bibliographic_couplings")
        or r.get("couplings")
        or r.get("results")
        or []
    )
    print(f"    返回顶层键: {list(r.keys())}")
    got = {}
    for item in pairs:
        if isinstance(item, dict):
            a = item.get("paper1_id") or item.get("paper_a") or item.get("source")
            b = item.get("paper2_id") or item.get("paper_b") or item.get("target")
            c = (
                item.get("coupling_strength")
                or item.get("count")
                or item.get("strength")
                or item.get("weight")
            )
            if a and b:
                got[norm((a, b))] = c
    ok = True
    for k, v in sorted(EXPECTED_COUPLING.items()):
        g = got.get(norm(k))
        if g != v:
            ok = False
        print(f"    {k}: 实得 {g}  {'ok' if g == v else f'✗ 期望 {v}'}")
    extra = set(got) - {norm(k) for k in EXPECTED_COUPLING}
    if extra:
        print(f"    ⚠ 多出未预期项: {sorted(extra)}")
    print(f"    → {'PASS' if ok and not extra else 'FAIL'}")
except Exception as e:
    print(f"    ✗ 抛出异常: {type(e).__name__}: {e}")

# ---------------- 网络指标 ----------------
print("\n[3] compute_metrics：基本量校验")
try:
    m = net.compute_metrics()
    for k, v in m.items():
        print(f"    {k}: {v}")
    # 解析真值
    print("\n    解析真值：6 节点、6 条边（有向），无自环")
except Exception as e:
    print(f"    ✗ 抛出异常: {type(e).__name__}: {e}")

# ---------------- 聚类 ----------------
print("\n[4] detect_research_clusters：能否在受控图上产出结果")
try:
    r = net.detect_research_clusters(min_cluster_size=2)
    print(f"    返回: {r if not isinstance(r, dict) else {k: (v if not isinstance(v, list) else f'[{len(v)} 项]') for k, v in r.items()}}")
except Exception as e:
    print(f"    ✗ 抛出异常: {type(e).__name__}: {e}")

# ---------------- 时间线 / 演进 ----------------
print("\n[5] citation_timeline / field_evolution")
for fn, arg in (("citation_timeline", "p3"), ("field_evolution", None)):
    try:
        r = getattr(net, fn)(arg) if arg else getattr(net, fn)()
        summary = r if not isinstance(r, dict) else {
            k: (f"[{len(v)} 项]" if isinstance(v, list) else v) for k, v in r.items()
        }
        print(f"    {fn}: {summary}")
    except Exception as e:
        print(f"    {fn} ✗ {type(e).__name__}: {e}")

# ---------------- 空图与边界 ----------------
print("\n[6] 边界：空网络")
try:
    empty = CitationNetwork()
    for fn in ("compute_metrics", "co_citation_analysis", "bibliographic_coupling"):
        try:
            r = getattr(empty, fn)()
            print(f"    {fn}(): {r if not isinstance(r, dict) else {k: (f'[{len(v)} 项]' if isinstance(v, list) else v) for k, v in r.items()}}")
        except Exception as e:
            print(f"    {fn}() ✗ {type(e).__name__}: {e}")
except Exception as e:
    print(f"    ✗ {type(e).__name__}: {e}")

print("\n" + "=" * 78)
