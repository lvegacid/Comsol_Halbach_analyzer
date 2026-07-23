# -*- coding: utf-8 -*-
"""
Created on Thu Jul 23 10:55:05 2026

@author: cidve
"""

import os
import sys
from datetime import datetime

import matplotlib as mpl
import numpy as np

file_path = r"Z:\Projects\Magnets\COMSOL_Simulation\NextHead\L500mm_Cubes25mm_Expected_5236ppmsLinear_128kg_longeFoV_240mmSymmetricUpdatedBHcurves\Simulation_results\Linear\Magnets_histogram_normH_Linear_50.0cm_25mm_5236ppmsLinear_128kg_longeFoV_24cmSymmetricFoV.txt"

Hlinear_end = None
Hknee = None
Hcb = None
Hcj = None
additional_H_values = [
    {"name": "Hextra", "value": 1500},
    {"name": "Htest", "value": 1425},
]


def compute_bin_edges(centers):
    centers = np.asarray(centers, dtype=float)
    if centers.size < 2:
        c = centers[0] if centers.size == 1 else 0.0
        return np.array([c - 0.5, c + 0.5], dtype=float)
    mids = 0.5 * (centers[:-1] + centers[1:])
    left = centers[0] - 0.5 * (centers[1] - centers[0])
    right = centers[-1] + 0.5 * (centers[-1] - centers[-2])
    return np.concatenate(([left], mids, [right]))


def cumulative_volume_percent_above(threshold, centers, weights):
    edges = compute_bin_edges(centers)
    weights = np.asarray(weights, dtype=float)
    widths = np.diff(edges)
    total = float(np.sum(widths * weights))
    if total <= 0:
        return 0.0

    thr = float(threshold)
    lefts = edges[:-1]
    rights = edges[1:]
    overlap = np.maximum(0.0, rights - np.maximum(thr, lefts))
    vol = float(np.sum(overlap * weights))
    return (vol / total) * 100.0


def _safe_float_or_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == "" or text.lower() in {"none", "nan"}:
            return None
        value = float(text)
    else:
        value = float(value)
    if not np.isfinite(value):
        return None
    if value == 0:
        return None
    return value


def _build_threshold_entries(Hlinear_end, Hknee, Hcb, Hcj, additional_H_values):
    entries = []

    predefined = [
        ("Hlinear_end", Hlinear_end, "royalblue"),
        ("Hknee", Hknee, "orange"),
        ("Hcb", Hcb, "green"),
        ("Hcj", Hcj, "purple"),
    ]
    for name, raw_value, color in predefined:
        value = _safe_float_or_none(raw_value)
        if value is not None:
            entries.append((name, value, color))

    extra_palette = ["teal", "brown", "magenta", "navy", "darkcyan", "olive"]
    raw_extras = additional_H_values
    if raw_extras is None:
        raw_extras = []
    if isinstance(raw_extras, dict):
        raw_extras = list(raw_extras.items())

    for idx, item in enumerate(raw_extras):
        if isinstance(item, dict):
            raw_name = item.get("name", "")
            raw_value = item.get("value", None)
        else:
            try:
                raw_name, raw_value = item
            except Exception:
                continue

        name = str(raw_name).strip()
        if name == "":
            continue
        value = _safe_float_or_none(raw_value)
        if value is None:
            continue
        color = extra_palette[idx % len(extra_palette)]
        entries.append((name, value, color))

    return entries


def process_histogram_h(
    file_path,
    Hlinear_end=None,
    Hknee=None,
    Hcb=None,
    Hcj=None,
    additional_H_values=None,
    output_path_H=None,
    show_plot=True,
):
    mpl.rcParams.update(mpl.rcParamsDefault)
    import matplotlib.pyplot as plt

    plt.style.use("default")
    plt.rcParams["figure.dpi"] = 100
    plt.rcParams["font.size"] = 10

    data_H = np.loadtxt(file_path, comments="%")
    H_kApm = data_H[:, 0]  # normH
    hist_H = data_H[:, 1]  # histogram
    hist_peak_raw = np.max(hist_H)
    if hist_peak_raw > 0:
        hist_H_norm = hist_H / hist_peak_raw
    else:
        hist_H_norm = np.zeros_like(hist_H)

    idx_max_H = np.argmax(hist_H)
    H_at_peak = H_kApm[idx_max_H]
    hist_H_max = hist_H_norm[idx_max_H]

    print(f"H en el maximo = {H_at_peak:.6f} kA/m")

    fig2, ax2 = plt.subplots(figsize=(8, 5))
    ax2.plot(H_kApm, hist_H_norm, color="grey")
    ax2.set_xlabel("Magnetic Field |H| (kA/m)")
    ax2.set_ylabel("Normalized histogram")
    fig2.suptitle(
        "Normalized normH histogram",
        y=0.94,
        fontstyle="italic",
    )

    color_max = "maroon"
    ax2.plot(H_at_peak, hist_H_max, ".", color=color_max)
    ax2.annotate(
        f"{H_at_peak:.4f} kA/m",
        xy=(H_at_peak, hist_H_max),
        xytext=(5, -15),
        textcoords="offset points",
        color=color_max,
    )

    total_volume = np.trapz(hist_H_norm, H_kApm)

    red_color = "red"
    mask_real = hist_H > 0

    H_real = H_kApm[mask_real]
    hist_real = hist_H[mask_real]

    H_min = np.min(H_real)
    H_max_real = np.max(H_real)
    H_avg = np.average(H_real, weights=hist_real)

    print("===================================")
    print(f"H_min  = {H_min:.6f} kA/m")
    print(f"H_avg  = {H_avg:.6f} kA/m")
    print(f"H_max  = {H_max_real:.6f} kA/m")
    print("===================================")

    labels = [
        f"Min {H_min:.3f} kA/m",
        f"Avg {H_avg:.3f} kA/m",
        f"Max {H_max_real:.3f} kA/m",
    ]

    def place_box_inside_x(ax, x_value, y_value, label_text, text_color, edge_color, offset_points=(8, 0)):
        # Place using offset points, then shift by measured bbox so it stays
        # fully inside axes horizontal bounds.
        text_artist = ax.annotate(
            label_text,
            xy=(x_value, y_value),
            xytext=offset_points,
            textcoords="offset points",
            rotation=0,
            va="center",
            ha="left",
            color=text_color,
            fontsize=9,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor=edge_color),
        )

        fig2.canvas.draw()
        r = fig2.canvas.get_renderer()
        tb = text_artist.get_window_extent(renderer=r)
        ab = ax.get_window_extent(renderer=r)
        pad_px = 4.0

        shift_px = 0.0
        if tb.x1 > ab.x1 - pad_px:
            shift_px = (ab.x1 - pad_px) - tb.x1
        elif tb.x0 < ab.x0 + pad_px:
            shift_px = (ab.x0 + pad_px) - tb.x0

        if abs(shift_px) > 0:
            x_pt, y_pt = text_artist.get_position()
            shift_pt = shift_px * 72.0 / fig2.dpi
            text_artist.set_position((x_pt + shift_pt, y_pt))

    ax2.axvline(H_min, color=red_color, linestyle=":", linewidth=1)
    place_box_inside_x(
        ax2,
        H_min,
        0.65,
        labels[0],
        red_color,
        "lightcoral",
        offset_points=(1, 0),
    )

    ax2.axvline(H_avg, color=red_color, linestyle=":", linewidth=1)
    place_box_inside_x(
        ax2,
        H_avg,
        0.8,
        labels[1],
        red_color,
        "lightcoral",
        offset_points=(-80, 0),
    )

    ax2.axvline(H_max_real, color=red_color, linestyle=":", linewidth=1)
    place_box_inside_x(
        ax2,
        H_max_real,
        0.65,
        labels[2],
        red_color,
        "lightcoral",
        offset_points=(1, 0),
    )

    thresholds = _build_threshold_entries(
        Hlinear_end=Hlinear_end,
        Hknee=Hknee,
        Hcb=Hcb,
        Hcj=Hcj,
        additional_H_values=additional_H_values,
    )

    threshold_metric_entries = []
    threshold_y = [0.52, 0.40, 0.28, 0.16, 0.54, 0.42, 0.30, 0.18]
    threshold_offset = [(-10, 0), (8, 0), (-10, 0), (8, 0), (-10, 0), (8, 0), (-10, 0), (8, 0)]

    plot_idx = 0
    for name, value, color in thresholds:
        ax2.axvline(value, color=color, linestyle="--", linewidth=1.2)
        place_box_inside_x(
            ax2,
            float(value),
            threshold_y[min(plot_idx, len(threshold_y) - 1)],
            f"{name} {float(value):.3f} kA/m",
            color,
            color,
            offset_points=threshold_offset[min(plot_idx, len(threshold_offset) - 1)],
        )

        vol_above = cumulative_volume_percent_above(value, H_kApm, hist_H)
        threshold_metric_entries.append((f"%{name}: {vol_above:.2f}%", color))
        plot_idx += 1

    hmax_metric_factors = [0.9, 0.8, 0.70, 0.60]
    hmax_metric_tokens = []
    for factor in hmax_metric_factors:
        thr = H_max_real * factor
        vol_above = cumulative_volume_percent_above(thr, H_kApm, hist_H)
        hmax_metric_tokens.append(
            f">{factor * 100:.0f}%({thr:.1f}): {vol_above:.2f}%"
        )

    summary_hmax = "%wrt Hmax: " + "    ".join(hmax_metric_tokens)
    summary_thresholds = threshold_metric_entries

    if summary_hmax or summary_thresholds:
        summary_y = 1.2
        summary_x0 = -0.05
        summary_w = 1.1
        summary_h = 0.14
        ax2.add_patch(
            plt.Rectangle(
                (summary_x0, summary_y - summary_h / 2.0),
                summary_w,
                summary_h,
                transform=ax2.transAxes,
                facecolor="white",
                edgecolor="gray",
                linewidth=1.0,
                clip_on=False,
            )
        )

    ax2.text(
    0.5,
    summary_y + 0.022,
    summary_hmax,
    transform=ax2.transAxes,
    ha="center",
    va="center",
    fontsize=9,
    color="green",
    clip_on=False,
    )
    
    if summary_thresholds:

        x = 0
    
        fig2.canvas.draw()
        renderer = fig2.canvas.get_renderer()
    
        for text, color in summary_thresholds:
    
            t = ax2.text(
                x,
                summary_y - 0.03,
                text,
                transform=ax2.transAxes,
                ha="left",
                va="center",
                fontsize=9,
                color=color,
                clip_on=False,
            )
    
            fig2.canvas.draw()
    
            bbox = t.get_window_extent(renderer=renderer)
    
            inv = ax2.transAxes.inverted()
    
            p0 = inv.transform((bbox.x0, bbox.y0))
            p1 = inv.transform((bbox.x1, bbox.y0))
    
            x += (p1[0] - p0[0]) + 0.02

    fecha = datetime.now().strftime("%Y-%m-%d")
    fig2.text(
        0.99,
        0.01,
        fecha,
        ha="right",
        va="bottom",
        fontsize=10,
        color="gray",
        alpha=0.8,
    )

    if output_path_H is None:
        output_path_H = os.path.splitext(file_path)[0] + "_Hfield.png"

    ax2.set_ylim(0, 1.05)
    fig2.subplots_adjust(
        left=0.10,
        right=0.94,
        bottom=0.18,
        top=0.72,
    )
    plt.savefig(output_path_H, dpi=300, bbox_inches="tight")

    if total_volume <= 0:
        print("Advertencia: volumen total normalizado nulo; revisar histograma de entrada.")

    if show_plot:
        plt.show()
    else:
        plt.close(fig2)

    return output_path_H



def _parse_value(raw):
    text = str(raw).strip()
    if text == "" or text.lower() in {"none", "nan"}:
        return None
    return float(text)


def _parse_cli_args(argv):
    # If arguments are provided, treat CLI execution as an explicit call
    # (e.g., from GUI integration) and avoid inheriting local test defaults.
    use_clean_cli_defaults = len(argv) > 0

    default_hlinear_end = Hlinear_end
    default_hknee = Hknee
    default_hcb = Hcb
    default_hcj = Hcj
    default_extra = additional_H_values

    if use_clean_cli_defaults:
        default_hlinear_end = None
        default_hknee = None
        default_hcb = None
        default_hcj = None
        default_extra = []

    parsed = {
        "file_path": file_path,
        "Hlinear_end": default_hlinear_end,
        "Hknee": default_hknee,
        "Hcb": default_hcb,
        "Hcj": default_hcj,
        "additional_H_values": default_extra,
        "output_path_H": None,
        "show_plot": True,
    }

    i = 0
    while i < len(argv):
        key = argv[i]
        if key == "--file-path" and i + 1 < len(argv):
            parsed["file_path"] = argv[i + 1]
            i += 2
            continue
        if key == "--Hlinear_end" and i + 1 < len(argv):
            parsed["Hlinear_end"] = _parse_value(argv[i + 1])
            i += 2
            continue
        if key == "--Hknee" and i + 1 < len(argv):
            parsed["Hknee"] = _parse_value(argv[i + 1])
            i += 2
            continue
        if key == "--Hcb" and i + 1 < len(argv):
            parsed["Hcb"] = _parse_value(argv[i + 1])
            i += 2
            continue
        if key == "--Hcj" and i + 1 < len(argv):
            parsed["Hcj"] = _parse_value(argv[i + 1])
            i += 2
            continue
        if key == "--output-png" and i + 1 < len(argv):
            parsed["output_path_H"] = argv[i + 1]
            i += 2
            continue
        if key == "--extra" and i + 1 < len(argv):
            token = str(argv[i + 1]).strip()
            if "=" not in token:
                raise ValueError(f"Invalid --extra format (expected Name=Value): {token}")
            name, raw_value = token.split("=", 1)
            name = name.strip()
            value = _parse_value(raw_value)
            extras = parsed.get("additional_H_values")
            if extras is None:
                extras = []
            if isinstance(extras, dict):
                extras = list(extras.items())
            extras.append((name, value))
            parsed["additional_H_values"] = extras
            i += 2
            continue
        if key == "--no-show":
            parsed["show_plot"] = False
            i += 1
            continue
        raise ValueError(f"Unknown or incomplete argument: {key}")

    return parsed


if __name__ == "__main__":
    args = _parse_cli_args(sys.argv[1:])
    process_histogram_h(
        file_path=args["file_path"],
        Hlinear_end=args["Hlinear_end"],
        Hknee=args["Hknee"],
        Hcb=args["Hcb"],
        Hcj=args["Hcj"],
        additional_H_values=args["additional_H_values"],
        output_path_H=args["output_path_H"],
        show_plot=args["show_plot"],
    )
