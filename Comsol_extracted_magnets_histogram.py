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
hist_M_norm = hist_M / np.max(hist_M)
M_percent = (M_T / Br) * 100

# Campo en el maximo

idx_max_M = np.argmax(hist_M)
M_max = M_T[idx_max_M]
hist_M_max = hist_M_norm[idx_max_M]

print(f"M en el maximo = {M_max:.6f} T")
print(f"M/Br en el maximo = {(M_max / Br) * 100:.4f} %")

# Plot

fig2, ax2 = plt.subplots(figsize=(8, 5))

ax2.plot(M_T, hist_M_norm, color="grey")
ax2.set_xlabel("Magnetization mu0|M| (T)")
ax2.set_ylabel("Normalized histogram")
ax2.set_title(
    case_title + "\n" + "Magnetization Histogram (Normalized)",
    pad=30,
    fontstyle="italic",
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

for i in range(len(percent_edges) - 1):
    p_min = percent_edges[i]
    p_max = percent_edges[i + 1]

    mask = (M_percent >= p_min) & (M_percent < p_max)

    if np.any(mask):
        volume_bin = np.trapz(hist_M_norm[mask], M_percent[mask])
        volume_percent = (volume_bin / total_volume) * 100
    else:
        volume_percent = 0.0

    ax2.axvline(percent_to_M(p_min), linestyle="--", linewidth=1.2, color=color)

    x_text = percent_to_M((p_min + p_max) / 2)
    if volume_percent >= 0.01:
        label_text = f"{volume_percent:.1f}%"
    else:
        label_text = f"{volume_percent:.1e}%"
    ax2.text(
        x_text,
        1.01,
        label_text,
        ha="center",
        va="bottom",
        fontsize=10,
        rotation=0,
        color=color,
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

for M_value, label in zip([M_min, M_avg, M_max_real], labels):
    ax2.axvline(M_value, color=red_color, linestyle=":", linewidth=1)
    ax2.text(
        M_value + 0.0015,
        0.75,
        label,
        rotation=0,
        va="center",
        ha="left",
        color=red_color,
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.8, edgecolor="lightcoral"),
    )

fecha = datetime.now().strftime("%Y-%m-%d")
fig2.text(0.99, 0.01, fecha, ha="right", va="bottom", fontsize=10, color="gray", alpha=0.8)

if args.output_png_m:
    output_path_M = args.output_png_m
elif args.same_name_png:
    output_path_M = os.path.splitext(file_path_M)[0] + ".png"
else:
    output_path_M = file_path_M.replace(".txt", "_magnetization.png")

plt.ylim(-0.1, 1.09)
plt.tight_layout()
plt.savefig(output_path_M, dpi=300, bbox_inches="tight")

if not args.no_show:
    plt.show()
