"""Draw cost against evaluated tours with a common scale for all methods."""

from algorithm.comparison import METHOD_COLORS, METHOD_NAMES


def draw_comparison_plot(canvas, reports, budget, current_evaluations=None):
    canvas.delete("all")
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width < 70 or height < 55:
        return
    if not reports:
        canvas.create_text(width / 2, height / 2, text="Run all three algorithms to compare costs.")
        return
    left, right, top, bottom = 55, width - 15, 58, height - 38
    if bottom <= top:
        top, bottom = 15, height - 20
    values = [value for report in reports.values() for value in report.result.history]
    low, high = min(values), max(values)
    span = high - low

    def point(evaluations, cost):
        return (left + evaluations / max(1, budget) * (right - left),
                (top + bottom) / 2 if span == 0 else bottom - (cost - low) / span * (bottom - top))

    canvas.create_line(left, top, left, bottom, right, bottom, fill="#657589")
    canvas.create_text(width / 2, height - 10, text="Tours evaluated", fill="#44576b")
    canvas.create_text(12, height / 2, text="Best cost", angle=90, fill="#44576b")
    canvas.create_text(left - 4, top, text=f"{high:.4g}", anchor="e", fill="#657589", font=("Segoe UI", 8))
    canvas.create_text(left - 4, bottom, text=f"{low:.4g}", anchor="e", fill="#657589", font=("Segoe UI", 8))
    canvas.create_text(left, height - 25, text="0", fill="#657589")
    canvas.create_text(right, height - 25, text=str(budget), anchor="e", fill="#657589")
    for index, method in enumerate(("aco", "nearest_neighbor", "random_search")):
        canvas.create_text(8, 8 + index * 15, text=METHOD_NAMES[method], anchor="nw",
                           fill=METHOD_COLORS[method], font=("Segoe UI", 9))
        if method not in reports:
            continue
        report = reports[method]
        color = METHOD_COLORS[method]
        if method == "nearest_neighbor":
            x1, y = point(0, report.result.best_length)
            x2, _ = point(budget, report.result.best_length)
            canvas.create_line(x1, y, x2, y, fill=color, dash=(5, 3), width=2, tags="nn-reference")
        else:
            points = [point(e, cost) for e, cost in zip(report.evaluation_history, report.result.history)]
            if len(points) > 1:
                canvas.create_line(*[v for p in points for v in p], fill=color, width=2,
                                   tags="aco-curve" if method == "aco" else "random-curve")
            x, y = points[-1]
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline="")
    if current_evaluations is not None:
        x, _ = point(current_evaluations, low)
        canvas.create_line(x, top, x, bottom, fill="#d66a24", dash=(3, 3), tags="history-cursor")
