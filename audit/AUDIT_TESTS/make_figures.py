from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "audit/results"
FIGURES = ROOT / "audit/figures"
FIGURES.mkdir(parents=True, exist_ok=True)


def svg_start(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="36" y="38" font-family="Arial" font-size="22" font-weight="700">{html.escape(title)}</text>',
    ]


def model_figure() -> None:
    data = pd.read_csv(RESULTS / "national_adjustment_metrics.csv")
    labels = {
        "A_direct_full_change_no_external_adjustment": "A cambio completo",
        "B_residualized_national_component": "B residual nacional",
        "C_current_repository": "C repositorio",
        "D_same_family_persistence": "D persistencia",
    }
    colors = ["#4575b4", "#91bfdb", "#d73027", "#777777"]
    width, height = 980, 560
    out = svg_start(width, height, "MAE ponderado por elección y alternativa")
    left, top, plot_w, plot_h = 80, 80, 850, 380
    max_y = 0.105
    for tick in range(0, 11, 2):
        value = tick / 100
        y = top + plot_h - value / max_y * plot_h
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#dddddd"/>')
        out.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="12">{tick}%</text>')
    years = [2018, 2021, 2024]
    bar_w = 48
    for yi, year in enumerate(years):
        group_x = left + 90 + yi * 280
        frame = data[data.target_year.eq(year)]
        for mi, (model, label) in enumerate(labels.items()):
            value = float(frame.loc[frame.model.eq(model), "weighted_mae"].iloc[0])
            h = value / max_y * plot_h
            x = group_x + mi * (bar_w + 6)
            y = top + plot_h - h
            out.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" fill="{colors[mi]}"/>')
            out.append(f'<text x="{x+bar_w/2}" y="{y-5:.1f}" text-anchor="middle" font-family="Arial" font-size="11">{100*value:.2f}</text>')
        out.append(f'<text x="{group_x+105}" y="{top+plot_h+28}" text-anchor="middle" font-family="Arial" font-size="15" font-weight="700">{year}</text>')
    for mi, (_, label) in enumerate(labels.items()):
        x = 80 + mi * 220
        out.append(f'<rect x="{x}" y="505" width="14" height="14" fill="{colors[mi]}"/>')
        out.append(f'<text x="{x+20}" y="517" font-family="Arial" font-size="12">{html.escape(label)}</text>')
    out.append('</svg>')
    (FIGURES / "model_comparison.svg").write_text("\n".join(out), encoding="utf-8")


def classifier_figure() -> None:
    data = pd.read_csv(RESULTS / "classifier_benchmarks.csv")
    data = data[data.target_year.eq(2024)]
    order = [
        "constant_train_prevalence",
        "historical_single_feature_logit",
        "simple_logistic",
        "current_time_calibrated",
        "current_inverted_diagnostic",
    ]
    labels = ["Constante train", "Histórico 1 variable", "Logístico simple", "Actual", "Actual invertido"]
    width, height = 920, 500
    out = svg_start(width, height, "Clasificador 2024 frente a baselines")
    left, top, plot_w, plot_h = 90, 85, 760, 310
    for tick in [0.3, 0.4, 0.5, 0.6, 0.7]:
        y = top + plot_h - (tick - 0.3) / 0.4 * plot_h
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#dddddd"/>')
        out.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="12">{tick:.1f}</text>')
    for i, (model, label) in enumerate(zip(order, labels, strict=True)):
        row = data[data.model.eq(model)].iloc[0]
        x = left + 45 + i * 145
        auc = float(row.roc_auc_weighted)
        pr = float(row.pr_auc_weighted)
        for j, (value, color) in enumerate([(auc, "#2166ac"), (pr, "#b2182b")]):
            h = (value - 0.3) / 0.4 * plot_h
            bx = x + j * 38
            y = top + plot_h - h
            out.append(f'<rect x="{bx}" y="{y:.1f}" width="32" height="{h:.1f}" fill="{color}"/>')
            out.append(f'<text x="{bx+16}" y="{y-5:.1f}" text-anchor="middle" font-family="Arial" font-size="10">{value:.3f}</text>')
        out.append(f'<text x="{x+18}" y="{top+plot_h+24}" text-anchor="middle" font-family="Arial" font-size="11">{html.escape(label)}</text>')
    out.append('<rect x="300" y="454" width="14" height="14" fill="#2166ac"/><text x="320" y="466" font-family="Arial" font-size="12">ROC-AUC</text>')
    out.append('<rect x="430" y="454" width="14" height="14" fill="#b2182b"/><text x="450" y="466" font-family="Arial" font-size="12">PR-AUC</text>')
    out.append('</svg>')
    (FIGURES / "classifier_2024_benchmarks.svg").write_text("\n".join(out), encoding="utf-8")


def calibration_figure() -> None:
    data = pd.read_csv(RESULTS / "classifier_2024_calibration.csv")
    width, height = 620, 560
    out = svg_start(width, height, "Calibración del clasificador actual en 2024")
    left, top, size = 80, 80, 420
    for tick in range(7):
        value = tick / 10
        x = left + value / 0.6 * size
        y = top + size - value / 0.6 * size
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+size}" stroke="#eeeeee"/>')
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+size}" y2="{y:.1f}" stroke="#eeeeee"/>')
        out.append(f'<text x="{x:.1f}" y="{top+size+20}" text-anchor="middle" font-family="Arial" font-size="11">{value:.1f}</text>')
        out.append(f'<text x="{left-12}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{value:.1f}</text>')
    out.append(f'<line x1="{left}" y1="{top+size}" x2="{left+size}" y2="{top}" stroke="#777" stroke-dasharray="5,5"/>')
    points = []
    for row in data.itertuples(index=False):
        x = left + min(float(row.mean_probability), 0.6) / 0.6 * size
        y = top + size - min(float(row.observed_rate), 0.6) / 0.6 * size
        points.append(f"{x:.1f},{y:.1f}")
    out.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="#d73027" stroke-width="3"/>')
    for point in points:
        x, y = point.split(",")
        out.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#d73027"/>')
    out.append(f'<text x="{left+size/2}" y="{top+size+48}" text-anchor="middle" font-family="Arial" font-size="13">Probabilidad media</text>')
    out.append(f'<text x="22" y="{top+size/2}" transform="rotate(-90 22 {top+size/2})" text-anchor="middle" font-family="Arial" font-size="13">Frecuencia observada</text>')
    out.append('</svg>')
    (FIGURES / "classifier_2024_calibration.svg").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    model_figure()
    classifier_figure()
    calibration_figure()
