"""图表生成服务 - matplotlib/plotly"""

import base64
import io
from typing import Any

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("services.chart")


class ChartGenerator:
    """图表生成器 - 支持matplotlib和plotly"""

    # 支持的图表类型
    SUPPORTED_CHART_TYPES = {
        "bar",
        "line",
        "pie",
        "scatter",
        "histogram",
        "box",
        "heatmap",
        "area",
        "violin",
        "radar",
        "citation_network",
        "trend",
        "co_citation",
    }

    @staticmethod
    def generate_matplotlib(
        chart_type: str,
        data: list[dict[str, Any]],
        options: dict[str, Any] = None,
        dpi: int = 150,
    ) -> dict[str, Any]:
        """使用matplotlib生成图表，返回base64图片"""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np  # noqa: F401 — 可用性检查
        except ImportError:
            raise ToolException(
                "matplotlib未安装，请运行: pip install matplotlib",
                tool_name="chart_generator",
            )

        options = options or {}
        title = options.get("title", "")
        xlabel = options.get("xlabel", "")
        ylabel = options.get("ylabel", "")
        figsize = tuple(options.get("figsize", [10, 6]))
        style = options.get("style", "seaborn-v0_8-whitegrid")
        color_scheme = options.get("colors", None)

        # 设置样式
        try:
            plt.style.use(style)
        except Exception:
            pass

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

        try:
            if chart_type == "bar":
                ChartGenerator._plot_bar(ax, data, options, color_scheme)
            elif chart_type == "line":
                ChartGenerator._plot_line(ax, data, options, color_scheme)
            elif chart_type == "pie":
                ChartGenerator._plot_pie(ax, data, options, color_scheme)
            elif chart_type == "scatter":
                ChartGenerator._plot_scatter(ax, data, options, color_scheme)
            elif chart_type == "histogram":
                ChartGenerator._plot_histogram(ax, data, options, color_scheme)
            elif chart_type == "box":
                ChartGenerator._plot_box(ax, data, options, color_scheme)
            elif chart_type == "heatmap":
                ChartGenerator._plot_heatmap(fig, ax, data, options, color_scheme)
            elif chart_type == "area":
                ChartGenerator._plot_area(ax, data, options, color_scheme)
            elif chart_type == "violin":
                ChartGenerator._plot_violin(ax, data, options, color_scheme)
            elif chart_type == "radar":
                ChartGenerator._plot_radar(fig, ax, data, options, color_scheme)
            elif chart_type == "trend":
                ChartGenerator._plot_trend(ax, data, options, color_scheme)
            elif chart_type == "citation_network":
                ChartGenerator._plot_citation_network(fig, ax, data, options)
            elif chart_type == "co_citation":
                ChartGenerator._plot_co_citation(fig, ax, data, options)
            else:
                raise ToolException(
                    f"不支持的图表类型: {chart_type}", tool_name="chart_generator"
                )

            ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
            if xlabel:
                ax.set_xlabel(xlabel, fontsize=11)
            if ylabel:
                ax.set_ylabel(ylabel, fontsize=11)

            plt.tight_layout()

            # 导出为base64
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode("utf-8")

            # 同时导出PDF字节（论文直接可用）
            pdf_buf = io.BytesIO()
            fig.savefig(pdf_buf, format="pdf", bbox_inches="tight")
            pdf_bytes = pdf_buf.getvalue()

            # 导出SVG
            svg_buf = io.BytesIO()
            fig.savefig(svg_buf, format="svg", bbox_inches="tight")
            svg_str = svg_buf.getvalue().decode("utf-8")

            return {
                "chart_type": chart_type,
                "image_base64": img_base64,
                "pdf_bytes_size": len(pdf_bytes),
                "svg_content": svg_str,
                "title": title,
                "format": "png+pdf+svg",
            }

        finally:
            plt.close(fig)

    @staticmethod
    def generate_plotly(
        chart_type: str, data: list[dict[str, Any]], options: dict[str, Any] = None
    ) -> dict[str, Any]:
        """使用plotly生成交互式图表，返回JSON配置"""
        try:
            import plotly.graph_objects as go
            import plotly.io as pio
        except ImportError:
            raise ToolException(
                "plotly未安装，请运行: pip install plotly", tool_name="chart_generator"
            )

        options = options or {}
        title = options.get("title", "")
        xlabel = options.get("xlabel", "")
        ylabel = options.get("ylabel", "")
        color_scheme = options.get("colors", None)

        fig = go.Figure()

        if chart_type == "bar":
            ChartGenerator._plotly_bar(fig, data, options, color_scheme)
        elif chart_type == "line":
            ChartGenerator._plotly_line(fig, data, options, color_scheme)
        elif chart_type == "scatter":
            ChartGenerator._plotly_scatter(fig, data, options, color_scheme)
        elif chart_type == "pie":
            ChartGenerator._plotly_pie(fig, data, options, color_scheme)
        elif chart_type == "heatmap":
            ChartGenerator._plotly_heatmap(fig, data, options, color_scheme)
        elif chart_type == "area":
            ChartGenerator._plotly_area(fig, data, options, color_scheme)
        elif chart_type == "violin":
            ChartGenerator._plotly_violin(fig, data, options, color_scheme)
        elif chart_type == "box":
            ChartGenerator._plotly_box(fig, data, options, color_scheme)
        elif chart_type == "trend":
            ChartGenerator._plotly_trend(fig, data, options, color_scheme)
        else:
            raise ToolException(
                f"plotly不支持该图表类型: {chart_type}", tool_name="chart_generator"
            )

        fig.update_layout(
            title=title,
            xaxis_title=xlabel,
            yaxis_title=ylabel,
            template="plotly_white",
            font=dict(size=12),
        )

        # 导出JSON
        plotly_json = pio.to_json(fig)
        # 导出静态PNG
        img_bytes = pio.to_image(fig, format="png", width=1000, height=600, scale=2)
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        return {
            "chart_type": chart_type,
            "plotly_json": plotly_json,
            "image_base64": img_base64,
            "title": title,
            "format": "plotly_json+png",
        }

    # ========== Matplotlib 绘图方法 ==========

    @staticmethod
    def _plot_bar(ax, data, options, color_scheme):
        import numpy as np

        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        labels = [str(d.get(x_key, "")) for d in data]
        values = [float(d.get(y_key, 0)) for d in data]
        colors = color_scheme or plt.cm.Set2(np.linspace(0, 1, len(labels)))
        ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.5)
        ax.tick_params(axis="x", rotation=45 if len(max(labels, key=len)) > 5 else 0)

    @staticmethod
    def _plot_line(ax, data, options, color_scheme):
        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        x_vals = [d.get(x_key) for d in data]
        y_vals = [float(d.get(y_key, 0)) for d in data]
        ax.plot(
            x_vals,
            y_vals,
            marker="o",
            linewidth=2,
            markersize=6,
            color=color_scheme[0] if color_scheme else None,
        )
        ax.fill_between(x_vals, y_vals, alpha=0.1)

    @staticmethod
    def _plot_pie(ax, data, options, color_scheme):
        labels_key = options.get("labels", "label")
        values_key = options.get("values", "value")
        labels = [str(d.get(labels_key, "")) for d in data]
        values = [float(d.get(values_key, 0)) for d in data]
        import numpy as np

        colors = color_scheme or plt.cm.Set3(np.linspace(0, 1, len(labels)))
        ax.pie(values, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)

    @staticmethod
    def _plot_scatter(ax, data, options, color_scheme):
        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        size_key = options.get("size", None)
        x_vals = [float(d.get(x_key, 0)) for d in data]
        y_vals = [float(d.get(y_key, 0)) for d in data]
        sizes = [float(d.get(size_key, 50)) for d in data] if size_key else 50
        ax.scatter(
            x_vals,
            y_vals,
            s=sizes,
            alpha=0.7,
            color=color_scheme[0] if color_scheme else None,
            edgecolors="white",
        )

    @staticmethod
    def _plot_histogram(ax, data, options, color_scheme):
        values_key = options.get("values", "value")
        bins = options.get("bins", 20)
        values = [float(d.get(values_key, 0)) for d in data]
        ax.hist(
            values,
            bins=bins,
            color=color_scheme[0] if color_scheme else "#4C72B0",
            edgecolor="white",
            alpha=0.8,
        )

    @staticmethod
    def _plot_box(ax, data, options, color_scheme):
        groups_key = options.get("groups", "groups")
        groups = data[0].get(groups_key, data) if data else data
        if isinstance(groups, list) and groups and isinstance(groups[0], list):
            ax.boxplot(groups, patch_artist=True)
        else:
            values_key = options.get("values", "value")
            group_key = options.get("group", "group")
            grouped = {}
            for d in data:
                g = d.get(group_key, "default")
                grouped.setdefault(g, []).append(float(d.get(values_key, 0)))
            if grouped:
                ax.boxplot(grouped.values(), labels=grouped.keys(), patch_artist=True)

    @staticmethod
    def _plot_heatmap(fig, ax, data, options, color_scheme):
        matrix_key = options.get("matrix", "matrix")
        matrix = data[0].get(matrix_key) if data else None
        if matrix is None:
            # 从data推断矩阵
            x_key = options.get("x", "x")
            y_key = options.get("y", "y")
            value_key = options.get("value", "value")
            x_labels = sorted(set(d.get(x_key, "") for d in data))
            y_labels = sorted(set(d.get(y_key, "") for d in data))
            matrix = [[0.0] * len(x_labels) for _ in range(len(y_labels))]
            for d in data:
                xi = x_labels.index(d.get(x_key, ""))
                yi = y_labels.index(d.get(y_key, ""))
                matrix[yi][xi] = float(d.get(value_key, 0))
            ax.set_xticks(range(len(x_labels)))
            ax.set_xticklabels(x_labels, rotation=45, ha="right")
            ax.set_yticks(range(len(y_labels)))
            ax.set_yticklabels(y_labels)

        im = ax.imshow(matrix, cmap=color_scheme or "YlOrRd", aspect="auto")
        fig.colorbar(im, ax=ax, shrink=0.8)

    @staticmethod
    def _plot_area(ax, data, options, color_scheme):
        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        x_vals = [d.get(x_key) for d in data]
        y_vals = [float(d.get(y_key, 0)) for d in data]
        ax.fill_between(
            x_vals,
            y_vals,
            alpha=0.4,
            color=color_scheme[0] if color_scheme else "#4C72B0",
        )
        ax.plot(x_vals, y_vals, linewidth=2)

    @staticmethod
    def _plot_violin(ax, data, options, color_scheme):
        values_key = options.get("values", "value")
        group_key = options.get("group", "group")
        grouped = {}
        for d in data:
            g = d.get(group_key, "default")
            grouped.setdefault(g, []).append(float(d.get(values_key, 0)))
        if grouped:
            positions = range(1, len(grouped) + 1)
            ax.violinplot(
                grouped.values(), positions=positions, showmeans=True, showmedians=True
            )
            ax.set_xticks(positions)
            ax.set_xticklabels(grouped.keys())

    @staticmethod
    def _plot_radar(fig, ax, data, options, color_scheme):
        import numpy as np

        ax.remove()
        ax = fig.add_subplot(111, polar=True)
        categories_key = options.get("categories", "categories")
        values_key = options.get("values", "values")
        for d in data:
            cats = d.get(categories_key, [])
            vals = d.get(values_key, [])
            if cats and vals:
                N = len(cats)  # noqa: N806
                angles = [n / float(N) * 2 * np.pi for n in range(N)]
                vals_plot = vals + [vals[0]]
                angles_plot = angles + [angles[0]]
                ax.plot(angles_plot, vals_plot, "o-", linewidth=2)
                ax.fill(angles_plot, vals_plot, alpha=0.15)
                ax.set_xticks(angles)
                ax.set_xticklabels(cats)

    @staticmethod
    def _plot_trend(ax, data, options, color_scheme):
        """引用趋势图"""
        year_key = options.get("year", "year")
        count_key = options.get("count", "count")
        years = [int(d.get(year_key, 0)) for d in data]
        counts = [int(d.get(count_key, 0)) for d in data]
        ax.bar(
            years,
            counts,
            color=color_scheme[0] if color_scheme else "#4C72B0",
            alpha=0.7,
            edgecolor="white",
        )
        ax.plot(years, counts, "o-", color="#E74C3C", linewidth=2, markersize=8)
        ax.set_xlabel("年份")
        ax.set_ylabel("引用次数")

    @staticmethod
    def _plot_citation_network(fig, ax, data, options):
        """引用关系网络图"""
        try:
            import networkx as nx
        except ImportError:
            raise ToolException(
                "networkx未安装，请运行: pip install networkx",
                tool_name="chart_generator",
            )

        G = nx.DiGraph()  # noqa: N806
        nodes_key = options.get("nodes", "nodes")
        edges_key = options.get("edges", "edges")

        nodes = data[0].get(nodes_key, []) if data else []
        edges = data[0].get(edges_key, []) if data else []

        for node in nodes:
            G.add_node(
                node.get("id", ""),
                label=node.get("title", node.get("id", "")),
                weight=node.get("citation_count", 1),
            )

        for edge in edges:
            G.add_edge(
                edge.get("source", ""),
                edge.get("target", ""),
                weight=edge.get("weight", 1),
            )

        if not G.nodes():
            ax.text(0.5, 0.5, "无引用关系数据", ha="center", va="center", fontsize=14)
            return

        pos = nx.spring_layout(G, k=2, iterations=50)
        weights = [G.nodes[n].get("weight", 1) for n in G.nodes()]
        max_w = max(weights) if weights else 1
        node_sizes = [300 + 2000 * (w / max_w) for w in weights]

        nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_size=node_sizes,
            node_color="#4C72B0",
            alpha=0.8,
            edgecolors="white",
        )
        nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            alpha=0.5,
            arrows=True,
            arrowstyle="-|>",
            arrowsize=15,
            connectionstyle="arc3,rad=0.1",
        )
        labels = {n: G.nodes[n].get("label", n)[:20] for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=8)
        ax.set_title("引用关系网络", fontsize=14, fontweight="bold")

    @staticmethod
    def _plot_co_citation(fig, ax, data, options):
        """共被引分析图"""
        try:
            import networkx as nx
        except ImportError:
            raise ToolException(
                "networkx未安装，请运行: pip install networkx",
                tool_name="chart_generator",
            )

        G = nx.Graph()  # noqa: N806
        pairs = data if isinstance(data, list) else []

        for item in pairs:
            p1 = item.get("paper1_id", item.get("paper1", ""))
            p2 = item.get("paper2_id", item.get("paper2", ""))
            weight = item.get("co_citation_count", item.get("weight", 1))
            if p1 and p2:
                G.add_node(p1, label=item.get("paper1_title", p1)[:20])
                G.add_node(p2, label=item.get("paper2_title", p2)[:20])
                G.add_edge(p1, p2, weight=weight)

        if not G.nodes():
            ax.text(0.5, 0.5, "无共被引数据", ha="center", va="center", fontsize=14)
            return

        pos = nx.spring_layout(G, k=1.5, iterations=50)
        edge_weights = [G[u][v]["weight"] for u, v in G.edges()]
        max_ew = max(edge_weights) if edge_weights else 1
        edge_widths = [1 + 5 * (w / max_ew) for w in edge_weights]

        nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_size=800,
            node_color="#E74C3C",
            alpha=0.8,
            edgecolors="white",
        )
        nx.draw_networkx_edges(G, pos, ax=ax, width=edge_widths, alpha=0.5)
        labels = {n: G.nodes[n].get("label", n) for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=8)
        ax.set_title("共被引分析网络", fontsize=14, fontweight="bold")

    # ========== Plotly 绘图方法 ==========

    @staticmethod
    def _plotly_bar(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        name_key = options.get("name", None)
        if name_key:
            # 分组柱状图
            groups = {}
            for d in data:
                g = d.get(name_key, "default")
                groups.setdefault(g, {"x": [], "y": []})
                groups[g]["x"].append(str(d.get(x_key, "")))
                groups[g]["y"].append(float(d.get(y_key, 0)))
            for g, vals in groups.items():
                fig.add_trace(go.Bar(x=vals["x"], y=vals["y"], name=g))
            fig.update_layout(barmode="group")
        else:
            labels = [str(d.get(x_key, "")) for d in data]
            values = [float(d.get(y_key, 0)) for d in data]
            fig.add_trace(go.Bar(x=labels, y=values, marker_color=color_scheme))

    @staticmethod
    def _plotly_line(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        x_vals = [d.get(x_key) for d in data]
        y_vals = [float(d.get(y_key, 0)) for d in data]
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers",
                line=dict(color=color_scheme[0] if color_scheme else None),
            )
        )

    @staticmethod
    def _plotly_scatter(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        text_key = options.get("text", None)
        x_vals = [float(d.get(x_key, 0)) for d in data]
        y_vals = [float(d.get(y_key, 0)) for d in data]
        texts = [str(d.get(text_key, "")) for d in data] if text_key else None
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="markers",
                text=texts,
                marker=dict(color=color_scheme[0] if color_scheme else None, size=10),
            )
        )

    @staticmethod
    def _plotly_pie(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        labels_key = options.get("labels", "label")
        values_key = options.get("values", "value")
        labels = [str(d.get(labels_key, "")) for d in data]
        values = [float(d.get(values_key, 0)) for d in data]
        fig.add_trace(go.Pie(labels=labels, values=values, marker_colors=color_scheme))

    @staticmethod
    def _plotly_heatmap(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        matrix_key = options.get("matrix", "matrix")
        z = data[0].get(matrix_key, []) if data else []
        x_key = options.get("x_labels", "x_labels")
        y_key = options.get("y_labels", "y_labels")
        x_labels = data[0].get(x_key, []) if data else []
        y_labels = data[0].get(y_key, []) if data else []
        fig.add_trace(
            go.Heatmap(z=z, x=x_labels, y=y_labels, colorscale=color_scheme or "YlOrRd")
        )

    @staticmethod
    def _plotly_area(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        x_key = options.get("x", "x")
        y_key = options.get("y", "y")
        x_vals = [d.get(x_key) for d in data]
        y_vals = [float(d.get(y_key, 0)) for d in data]
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                fill="tozeroy",
                mode="lines",
                line=dict(color=color_scheme[0] if color_scheme else None),
            )
        )

    @staticmethod
    def _plotly_violin(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        values_key = options.get("values", "value")
        group_key = options.get("group", "group")
        grouped = {}
        for d in data:
            g = d.get(group_key, "default")
            grouped.setdefault(g, []).append(float(d.get(values_key, 0)))
        for g, vals in grouped.items():
            fig.add_trace(
                go.Violin(y=vals, name=g, box_visible=True, meanline_visible=True)
            )

    @staticmethod
    def _plotly_box(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        values_key = options.get("values", "value")
        group_key = options.get("group", "group")
        grouped = {}
        for d in data:
            g = d.get(group_key, "default")
            grouped.setdefault(g, []).append(float(d.get(values_key, 0)))
        for g, vals in grouped.items():
            fig.add_trace(go.Box(y=vals, name=g))

    @staticmethod
    def _plotly_trend(fig, data, options, color_scheme):
        import plotly.graph_objects as go

        year_key = options.get("year", "year")
        count_key = options.get("count", "count")
        years = [int(d.get(year_key, 0)) for d in data]
        counts = [int(d.get(count_key, 0)) for d in data]
        fig.add_trace(
            go.Bar(
                x=years,
                y=counts,
                name="引用次数",
                marker_color=color_scheme[0] if color_scheme else "#4C72B0",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=years,
                y=counts,
                mode="lines+markers",
                name="趋势线",
                line=dict(color="#E74C3C", width=2),
            )
        )

    @staticmethod
    def generate_chart_config(
        chart_type: str, data: list[dict[str, Any]], options: dict[str, Any] = None
    ) -> dict[str, Any]:
        """根据图表类型自动选择最佳生成方式，返回配置建议"""
        static_types = {
            "histogram",
            "radar",
            "citation_network",
            "co_citation",
            "trend",
        }

        if chart_type in static_types:
            engine = "matplotlib"
        elif options and options.get("engine") == "matplotlib":
            engine = "matplotlib"
        else:
            engine = "plotly"

        # 自动推断x/y键
        if data and not options:
            sample = data[0]
            keys = list(sample.keys())
            options = {}
            numeric_keys = [k for k in keys if isinstance(sample.get(k), (int, float))]
            string_keys = [k for k in keys if isinstance(sample.get(k), str)]

            if chart_type == "pie":
                if string_keys:
                    options["labels"] = string_keys[0]
                if numeric_keys:
                    options["values"] = numeric_keys[0]
            else:
                if string_keys:
                    options["x"] = string_keys[0]
                if numeric_keys:
                    options["y"] = numeric_keys[0]

        return {
            "chart_type": chart_type,
            "recommended_engine": engine,
            "options": options or {},
            "data_points": len(data),
        }


# 引入plt用于类方法
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
