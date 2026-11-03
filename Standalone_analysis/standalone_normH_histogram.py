# -*- coding: utf-8 -*-
"""
Standalone normH histogram plot for magnet analysis (no GUI, no CLI).

Edit the CONFIGURATION block and run:  python standalone_normH_histogram.py

Input : COMSOL 2-column .txt (normH [kA/m], histogram counts); '%' lines are comments.
Output: PNG with the normalized histogram, Min/Avg/Max/Peak markers,
        threshold lines and the % of volume above each threshold.
"""

import os
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # file output only, no GUI backend
import matplotlib.pyplot as plt
import numpy as np

# =============================== CONFIGURATION ===============================
TXT_FILE_PATH = r"Z:\Projects\Magnets\COMSOL_Simulation\Next\Nonlinear_simulation\Simulation_results\N48Linear_Br1_4_mur1_05\Magnets_histogram50bins_normH_N48Linear_Br1_4_mur1_05_Original_2layers_19mm_19rings.txt"
OUTPUT_PNG_PATH = None  # None -> <TXT_FILE_PATH without extension>_Hfield.png

# Threshold markers in kA/m (None or 0 -> not drawn)
Hlinear_end = 813
Hknee = None
Hcb = None
Hcj = None
# Custom thresholds: {"name": ..., "value": kA/m}
ADDITIONAL_THRESHOLDS = [
    {"name": "Hextra", "value": None},
    {"name": "Htest", "value": None},
]

# Display options
TITLE = "Normalized normH histogram"
X_LABEL = "Magnetic Field |H| (kA/m)"
Y_LABEL = "Normalized histogram"
TITLE_FONT_SIZE = 12
LABEL_FONT_SIZE = 10
ANNOTATION_FONT_SIZE = 9
PLOT_STYLE = "bars"  # "bars" or "line"
BAR_COLOR = "lightgrey"
FIGURE_SIZE = (5, 5)
DPI = 300
SHOW_DATE = False
SHOW_PEAK_ANNOTATION = True
SHOW_MIN_AVG_MAX = True
SHOW_THRESHOLDS = True
SHOW_SUMMARY_BOX = False  # % volume above thresholds / fractions of Hmax
HMAX_FRACTIONS = [0.9, 0.8, 0.7, 0.6]  # for "%wrt Hmax" in the summary box
# ============================================================================

EXTRA_PALETTE = ["teal", "brown", "magenta", "navy", "darkcyan", "olive"]
# Vertical position (axes fraction) and x offset (points) for threshold labels
THRESHOLD_Y = [0.52, 0.40, 0.28, 0.16, 0.54, 0.42, 0.30, 0.18]
THRESHOLD_OFFSET = [(-10, 0), (8, 0), (-10, 0), (8, 0)] * 2


def compute_bin_edges(centers):
    centers = np.asarray(centers, dtype=float)
    if centers.size < 2:
        c = centers[0] if centers.size == 1 else 0.0
        return np.array([c - 0.5, c + 0.5])
    mids = 0.5 * (centers[:-1] + centers[1:])
    left = centers[0] - 0.5 * (centers[1] - centers[0])
    right = centers[-1] + 0.5 * (centers[-1] - centers[-2])
    return np.concatenate(([left], mids, [right]))


def volume_percent_above(threshold, centers, weights):
    edges = compute_bin_edges(centers)
    weights = np.asarray(weights, dtype=float)
    total = float(np.sum(np.diff(edges) * weights))
    if total <= 0:
        return 0.0
    overlap = np.maximum(0.0, edges[1:] - np.maximum(float(threshold), edges[:-1]))
    return float(np.sum(overlap * weights)) / total * 100.0


def _valid_value(raw):
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) and value != 0 else None


def build_thresholds():
    entries = []
    for name, raw, color in [
        ("H_linear_end_N48", Hlinear_end, "royalblue"),
        ("Hknee", Hknee, "orange"),
        ("Hcb", Hcb, "green"),
        ("Hcj", Hcj, "purple"),
    ]:
        value = _valid_value(raw)
        if value is not None:
            entries.append((name, value, color))

    for idx, item in enumerate(ADDITIONAL_THRESHOLDS or []):
        name = str(item.get("name", "")).strip()
        value = _valid_value(item.get("value"))
        if name and value is not None:
            entries.append((name, value, EXTRA_PALETTE[idx % len(EXTRA_PALETTE)]))
    return entries


def place_box_inside_x(fig, ax, x, y, text, color, edge_color, offset):
    """Annotate at (x, y) and shift horizontally so the box stays inside the axes."""
    artist = ax.annotate(
        text,
        xy=(x, y),
        xytext=offset,
        textcoords="offset points",
        va="center",
        ha="left",
        color=color,
        fontsize=ANNOTATION_FONT_SIZE,
        bbox=dict(facecolor="white", alpha=0.8, edgecolor=edge_color),
    )
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    tb = artist.get_window_extent(renderer=renderer)
    ab = ax.get_window_extent(renderer=renderer)
    pad = 4.0
    shift_px = 0.0
    if tb.x1 > ab.x1 - pad:
        shift_px = (ab.x1 - pad) - tb.x1
    elif tb.x0 < ab.x0 + pad:
        shift_px = (ab.x0 + pad) - tb.x0
    if shift_px:
        x_pt, y_pt = artist.get_position()
        artist.set_position((x_pt + shift_px * 72.0 / fig.dpi, y_pt))


def load_histogram(path):
    data = np.loadtxt(path, comments="%")
    data = np.atleast_2d(data)
    if data.shape[1] < 2:
        raise ValueError("Expected a 2-column file (normH, histogram).")
    return data[:, 0], data[:, 1]


def main():
    H, hist = load_histogram(TXT_FILE_PATH)

    peak_raw = np.max(hist)
    hist_norm = hist / peak_raw if peak_raw > 0 else np.zeros_like(hist)
    idx_peak = int(np.argmax(hist))
    H_peak, y_peak = H[idx_peak], hist_norm[idx_peak]

    mask = hist > 0
    if not np.any(mask):
        raise ValueError("Histogram has no positive bins; check the input file.")
    H_min = float(np.min(H[mask]))
    H_max = float(np.max(H[mask]))
    H_avg = float(np.average(H[mask], weights=hist[mask]))

    print("===================================")
    print(f"H_min  = {H_min:.6f} kA/m")
    print(f"H_avg  = {H_avg:.6f} kA/m")
    print(f"H_max  = {H_max:.6f} kA/m")
    print(f"H_peak = {H_peak:.6f} kA/m")
    print("===================================")

    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    if PLOT_STYLE == "bars":
        edges = compute_bin_edges(H)
        ax.bar(edges[:-1], hist_norm, width=np.diff(edges), align="edge",
               color=BAR_COLOR, edgecolor="grey", linewidth=0.5)
    else:
        ax.plot(H, hist_norm, color="grey")
    ax.set_xlabel(X_LABEL, fontsize=LABEL_FONT_SIZE)
    ax.set_ylabel(Y_LABEL, fontsize=LABEL_FONT_SIZE)
    ax.tick_params(labelsize=LABEL_FONT_SIZE)
    #fig.suptitle(TITLE, y=0.94, fontstyle="italic", fontsize=TITLE_FONT_SIZE)
    ax.set_ylim(0, 1.05)
    fig.subplots_adjust(left=0.10, right=0.94, bottom=0.18, top=0.72)

    if SHOW_PEAK_ANNOTATION:
        ax.plot(H_peak, y_peak, ".", color="maroon")
        ax.annotate(
            f"{H_peak:.4f} kA/m",
            xy=(H_peak, y_peak),
            xytext=(5, -15),
            textcoords="offset points",
            color="maroon",
            fontsize=ANNOTATION_FONT_SIZE,
        )

    if SHOW_MIN_AVG_MAX:
        for value, label, y, offset in [
            (H_min, f"Min {H_min:.3f} kA/m", 0.65, (1, 0)),
            (H_avg, f"Avg {H_avg:.3f} kA/m", 0.80, (-80, 0)),
            (H_max, f"Max {H_max:.3f} kA/m", 0.65, (1, 0)),
        ]:
            ax.axvline(value, color="red", linestyle=":", linewidth=1)
            place_box_inside_x(fig, ax, value, y, label, "red", "lightcoral", offset)

    thresholds = build_thresholds()
    threshold_metrics = []
    for idx, (name, value, color) in enumerate(thresholds):
        pct = volume_percent_above(value, H, hist)
        threshold_metrics.append((f"%{name}: {pct:.2f}%", color))
        print(f"{name} = {value:.3f} kA/m -> {pct:.2f}% of volume above")
        if SHOW_THRESHOLDS:
            ax.axvline(value, color=color, linestyle="--", linewidth=1.2)
            i = min(idx, len(THRESHOLD_Y) - 1)
            place_box_inside_x(
                fig, ax, value, THRESHOLD_Y[i], f"{name} {value:.3f} kA/m",
                color, color, THRESHOLD_OFFSET[i],
            )

    if SHOW_SUMMARY_BOX:
        hmax_tokens = [
            f">{f * 100:.0f}%({H_max * f:.1f}): {volume_percent_above(H_max * f, H, hist):.2f}%"
            for f in HMAX_FRACTIONS
        ]
        summary_hmax = "%wrt Hmax: " + "    ".join(hmax_tokens)
        y0, box_h = 1.2, 0.14
        ax.add_patch(
            plt.Rectangle(
                (-0.05, y0 - box_h / 2.0), 1.1, box_h,
                transform=ax.transAxes, facecolor="white", edgecolor="gray",
                linewidth=1.0, clip_on=False,
            )
        )
        ax.text(
            0.5, y0 + 0.022, summary_hmax, transform=ax.transAxes, ha="center",
            va="center", fontsize=ANNOTATION_FONT_SIZE, color="green", clip_on=False,
        )

        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        inv = ax.transAxes.inverted()
        x = 0.0
        for text, color in threshold_metrics:
            t = ax.text(
                x, y0 - 0.03, text, transform=ax.transAxes, ha="left", va="center",
                fontsize=ANNOTATION_FONT_SIZE, color=color, clip_on=False,
            )
            bbox = t.get_window_extent(renderer=renderer)
            x += inv.transform((bbox.x1, bbox.y0))[0] - inv.transform((bbox.x0, bbox.y0))[0] + 0.02

    if SHOW_DATE:
        fig.text(
            0.99, 0.01, datetime.now().strftime("%Y-%m-%d"),
            ha="right", va="bottom", fontsize=LABEL_FONT_SIZE, color="gray", alpha=0.8,
        )

    out = OUTPUT_PNG_PATH or os.path.splitext(TXT_FILE_PATH)[0] + "_Hfield.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
