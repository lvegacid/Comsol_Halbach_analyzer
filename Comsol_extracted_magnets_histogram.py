import argparse
import os
from datetime import datetime

import matplotlib as mpl
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Magnets histogram postprocess")
    parser.add_argument("--file-path-m", dest="file_path_m", required=True, help="Ruta al TXT Magnets histogram")
    parser.add_argument("--magnet-info", dest="magnet_info", default="N/A", help="Texto Magnet_info")
    parser.add_argument("--analysis", dest="analysis", default="N/A", help="Texto Analysis")
    parser.add_argument("--output-png-m", dest="output_png_m", help="Ruta PNG de salida para Magnets")
    parser.add_argument("--br", dest="br", type=float, default=1.4, help="Br en Tesla")
    parser.add_argument("--step-percent", dest="step_percent", type=float, default=2.0, help="Paso porcentual para bins")
    parser.add_argument("--same-name-png", action="store_true", help="Guardar como <txt>.png")
    parser.add_argument("--no-show", action="store_true", help="No abrir ventanas de plot")
    return parser.parse_args()


args = parse_args()

if args.no_show:
    mpl.use("Agg")

import matplotlib.pyplot as plt

mpl.rcParams.update(mpl.rcParamsDefault)
plt.style.use("default")
plt.rcParams["figure.dpi"] = 100
plt.rcParams["font.size"] = 10

file_path_M = args.file_path_m
Br = float(args.br)
step_percent = float(args.step_percent)

if not np.isfinite(Br) or Br <= 0:
    raise ValueError("Br debe ser mayor a 0")
if not np.isfinite(step_percent) or step_percent <= 0:
    raise ValueError("step_percent debe ser mayor a 0")

case_title = f"Magnet: {args.magnet_info}, Analysis: {args.analysis}"

# Lectura del archivo

data_M = np.loadtxt(file_path_M, comments="%")
M_T = data_M[:, 0]  # mu0_const*mfnc.normM (T)
hist_M = data_M[:, 1]
hist_peak_raw = np.max(hist_M)
if hist_peak_raw > 0:
    hist_M_norm = hist_M / hist_peak_raw
else:
    hist_M_norm = np.zeros_like(hist_M)
M_percent = (M_T / Br) * 100

# Campo en el maximo

idx_max_M = np.argmax(hist_M)
M_max = M_T[idx_max_M]
hist_M_max = hist_M_norm[idx_max_M]

print(f"M en el maximo = {M_max:.6f} T")
print(f"M/Br en el maximo = {(M_max / Br) * 100:.4f} %")

fig2, ax2 = plt.subplots(figsize=(8, 5))
ax2.plot(M_T, hist_M_norm, color="grey")
ax2.set_xlabel("Magnetization mu0|M| (T)")
ax2.set_ylabel("Normalized histogram")
fig2.suptitle(
    case_title + "\n" + "Magnetization Histogram (Normalized)",
    y=0.94,
    fontstyle="italic"
)

color_max = "maroon"
ax2.plot(M_max, hist_M_max, ".", color=color_max)
ax2.annotate(
    f"{M_max:.4f} T",
    xy=(M_max, hist_M_max),
    xytext=(5, -15),
    textcoords="offset points",
    color=color_max,
)


def M_to_percent(M_value):
    return (M_value / Br) * 100


def percent_to_M(percent):
    return (percent / 100) * Br


secax2 = ax2.secondary_xaxis("top", functions=(M_to_percent, percent_to_M))
secax2.set_xlabel("Magnetization (% of Br)")

color = "royalblue"

p_min_data = np.min(M_percent)
p_max_data = np.max(M_percent)

p_start = step_percent * np.floor(p_min_data / step_percent)
p_end = step_percent * np.ceil(p_max_data / step_percent)

percent_edges = np.arange(p_start, p_end + step_percent, step_percent)
secax2.set_xticks(percent_edges)
secax2.set_xticklabels([f"{p:.0f}" for p in percent_edges])

total_volume = np.trapz(hist_M_norm, M_percent)


def compute_bin_edges(centers):
    centers = np.asarray(centers, dtype=float)
    if centers.size < 2:
        c = centers[0] if centers.size == 1 else 0.0
        return np.array([c - 0.5, c + 0.5], dtype=float)
    mids = 0.5 * (centers[:-1] + centers[1:])
    left = centers[0] - 0.5 * (centers[1] - centers[0])
    right = centers[-1] + 0.5 * (centers[-1] - centers[-2])
    return np.concatenate(([left], mids, [right]))


def interval_volume_percent(interval_min, interval_max, centers, weights):
    edges = compute_bin_edges(centers)
    weights = np.asarray(weights, dtype=float)
    widths = np.diff(edges)
    total = float(np.sum(widths * weights))
    if total <= 0:
        return 0.0

    a = float(interval_min)
    b = float(interval_max)
    lefts = edges[:-1]
    rights = edges[1:]
    overlap = np.maximum(0.0, np.minimum(b, rights) - np.maximum(a, lefts))
    vol = float(np.sum(overlap * weights))
    return (vol / total) * 100.0


def cumulative_volume_percent_below(threshold_percent, centers, weights):
    edges = compute_bin_edges(centers)
    weights = np.asarray(weights, dtype=float)
    widths = np.diff(edges)
    total = float(np.sum(widths * weights))
    if total <= 0:
        return 0.0

    thr = float(threshold_percent)
    lefts = edges[:-1]
    rights = edges[1:]
    overlap = np.maximum(0.0, np.minimum(thr, rights) - lefts)
    vol = float(np.sum(overlap * weights))
    return (vol / total) * 100.0

for i in range(len(percent_edges) - 1):
    p_min = percent_edges[i]
    p_max = percent_edges[i + 1]

    volume_percent = interval_volume_percent(p_min, p_max, M_percent, hist_M)

    ax2.axvline(percent_to_M(p_min), linestyle="--", linewidth=1.2, color=color)

    x_text = percent_to_M((p_min + p_max) / 2)
    if volume_percent >= 0.01:
        label_text = f"{volume_percent:.1f}%"
    else:
        label_text = f"{volume_percent:.1e}%"
    ax2.text(
        x_text,
        1.01 + (0.02 if (i % 2) else 0.0),
        label_text,
        ha="center",
        va="bottom",
        fontsize=8,
        rotation=0,
        color=color,
    )

# ============================================================
# Summary metrics (<98, <95, <90, <85) + WDV (from TXT histogram)
# ============================================================
V_lt_98 = cumulative_volume_percent_below(98.0, M_percent, hist_M)
V_lt_95 = cumulative_volume_percent_below(95.0, M_percent, hist_M)
V_lt_90 = cumulative_volume_percent_below(90.0, M_percent, hist_M)
V_lt_85 = cumulative_volume_percent_below(85.0, M_percent, hist_M)
V_lt_80 = cumulative_volume_percent_below(80.0, M_percent, hist_M)

wdv = (
    0.5 * V_lt_98
    + 1.0 * V_lt_95
    + 2.0 * V_lt_90
    + 5.0 * V_lt_85
    + 10.0 * V_lt_80
)

summary_y = 1.2
summary_x0 = 0.05
summary_w = 0.95
summary_h = 0.11
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

summary_text_main = (
    f"<98% Br: {V_lt_98:.1f}%      "
    f"<95% Br: {V_lt_95:.1f}%      "
    f"<90% Br: {V_lt_90:.1f}%      "
    f"<85% Br: {V_lt_85:.1f}%"
)

ax2.text(
    0.4,
    summary_y,
    summary_text_main,
    transform=ax2.transAxes,
    ha="center",
    va="center",
    fontsize=9,
    color="green",
    clip_on=False,
)

ax2.text(
    0.84,
    summary_y,
    f"       WDV: {wdv:.2f}",
    transform=ax2.transAxes,
    ha="center",
    va="center",
    fontsize=10,
    color="red",
    fontweight="bold",
    clip_on=False,
)

red_color = "red"
mask_real = hist_M > 0

M_real = M_T[mask_real]
hist_real = hist_M[mask_real]

M_min = np.min(M_real)
M_max_real = np.max(M_real)
M_avg = np.average(M_real, weights=hist_real)

print("===================================")
print(f"M_min  = {M_min:.6f} T")
print(f"M_avg  = {M_avg:.6f} T")
print(f"M_max  = {M_max_real:.6f} T")
print("===================================")


def to_percent(M_value):
    return (M_value / Br) * 100


labels = [
    f"Min\n{M_min:.3f} T ({to_percent(M_min):.1f}%)",
    f"Avg\n {M_avg:.3f} T ({to_percent(M_avg):.1f}%)",
    f"Max\n {M_max_real:.3f} T ({to_percent(M_max_real):.1f}%)",
]

span_x = max(np.max(M_T) - np.min(M_T), 1e-9)
dx = 0.015 * span_x


def place_box_inside_x(ax, x_value, y_value, label_text, text_color, edge_color, offset_points=(8,0)):
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

# Min
ax2.axvline(M_min, color=red_color, linestyle=":", linewidth=1)
place_box_inside_x(
    ax2,
    M_min,
    0.65,
    labels[0],
    red_color,
    "lightcoral",
    offset_points=(1, 0),
)

# Average
ax2.axvline(M_avg, color=red_color, linestyle=":", linewidth=1)
place_box_inside_x(
    ax2,
    M_avg,
    0.8,
    labels[1],
    red_color,
    "lightcoral",
    offset_points=(-80, 0),
)

# Max (hacia la izquierda para que no se solape)
ax2.axvline(M_max_real, color=red_color, linestyle=":", linewidth=1)
place_box_inside_x(
    ax2,
    M_max_real,
    0.65,
    labels[2],
    red_color,
    "lightcoral",
    offset_points=(1, 0),
)

# Br
ax2.axvline(Br, color=red_color, linestyle=":", linewidth=1)
place_box_inside_x(
    ax2,
    Br,
    0.42,
    f"Br\n{Br:.3f} T (100.0%)",
    color,
    "lightskyblue",
    offset_points=(1, -30),
)

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

if args.output_png_m:
    output_path_M = args.output_png_m
elif args.same_name_png:
    output_path_M = os.path.splitext(file_path_M)[0] + ".png"
else:
    output_path_M = file_path_M.replace(".txt", "_magnetization.png")

fig2.text(
    0.5,
    0.025,
    "Weighted Demagnetized Volume (WDV) = 0.5·V<98% + 1·V<95% + 2·V<90% + 5·V<85% + 10·V<80%",
    ha="center",
    va="bottom",
    fontsize=8,
    color="gray",
)
fig2.text(
    0.5,
    0.005,
    "where V<x% is the cumulative magnet volume below x% of Br.",
    ha="center",
    va="bottom",
    fontsize=8,
    color="gray",
)

ax2.set_ylim(0, 1.05)
fig2.subplots_adjust(
    left=0.10,
    right=0.94,
    bottom=0.18,
    top=0.72,
)
plt.savefig(output_path_M, dpi=300, bbox_inches="tight")

if not args.no_show:
    plt.show()
