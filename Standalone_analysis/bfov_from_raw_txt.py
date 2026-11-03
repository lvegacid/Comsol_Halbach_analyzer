from datetime import datetime
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

COMSOL_TXT_HISTOGRAM = False
COMSOL_HISTOGRAM_PATH = r"Z:\Projects\Magnets\COMSOL_Simulation\Preclinico\Different_FOVs\N45SH\B_FOV_Ellipsoid37_5x39x39_SURFACE_Histogram_Preclinico_study_FOV_measurement.txt"

# ============================================================
# CONFIGURACION FACIL DE EDITAR
# ============================================================

# TXT_PATH = r"Z:\Projects\Magnets\COMSOL_Simulation\Preclinico\Different_FOVs\N45SH\CylinderD100H100\Step7_5mm\B_coordinates_FromFile_Coordenadas_sensor_cilindro_D_0_100_L_0_100_step_0_0075_cols_1_2_3.txt"
TXT_PATH = r"Z:\Projects\Preclinico\Medidas\20260926 1805 Preclinico 10cm9cm_1cm 1000avg 200medidas_20260926_180547.txt"
# Histograma
BINS = 100
MAGNET_INFO = ""
FOV_INFO = "Raw TXT"
ANALYSIS = ""

# Columnas del TXT, 1-based.
# Deja VALUE_COL en la columna que quieras colorear, por ejemplo By en mT.
X_COL = 1
Y_COL = 2
Z_COL = 3
VALUE_COL = 5

# 3D
POINT_SIZE = 50
CMAP = "inferno"
OUTPUT_PNG = ""
TITLE = "Magnetic flux density, y-component (mT)"
VALUE_LABEL = "By (mT)"
AXIS_UNIT = "m"
SHOW_PLOT = True


mpl.rcParams.update(mpl.rcParamsDefault)
plt.style.use("default")
plt.rcParams["figure.dpi"] = 100
plt.rcParams["font.size"] = 10


def _build_histogram_outputs(base_path):
    stem = base_path.stem
    histogram_txt = base_path.with_name(f"BFOV_histogram_{stem}.txt")
    histogram_norm_txt = base_path.with_name(f"BFOV_histogram_{stem}_normalized.txt")
    histogram_png = base_path.with_name(f"BFOV_histogram_{stem}_BFOV.png")
    return stem, histogram_txt, histogram_norm_txt, histogram_png


def _plot_and_save_histogram(b_values, histogram_txt, histogram_norm_txt, histogram_png, magnet_info, analysis_info):
    gamma = 42.58e6

    COL_MINMAX = "red"
    COL_PEAK = "orchid"
    COLOR_FWHM = "magenta"
    COL_P1 = "royalblue"
    COL_P5 = "green"
    COL_BOX_EDGE = "grey"

    LS_MINMAX = ":"
    LS_PERCENT = "--"

    bins = max(1, int(BINS))
    b_min_raw = float(np.min(b_values))
    b_max_raw = float(np.max(b_values))
    if b_max_raw <= b_min_raw:
        delta = max(1e-12, abs(b_min_raw) * 1e-6 + 1e-12)
        b_min_raw -= delta
        b_max_raw += delta

    edges = np.linspace(b_min_raw, b_max_raw, bins + 1)
    hist, edges = np.histogram(b_values, bins=edges)
    B_mT = 0.5 * (edges[:-1] + edges[1:])
    hist = hist.astype(float)

    np.savetxt(histogram_txt, np.column_stack((B_mT, hist)), fmt="%.15g", delimiter="\t")

    if np.max(hist) > 0:
        hist_norm = hist / np.max(hist)
    else:
        hist_norm = np.zeros_like(hist)
    np.savetxt(histogram_norm_txt, np.column_stack((B_mT, hist_norm)), fmt="%.15g", delimiter="\t")

    mask_hist = hist > 0
    if not np.any(mask_hist):
        raise ValueError("El histograma resultante esta vacio")

    B_real = B_mT[mask_hist]
    hist_real = hist[mask_hist]

    B_min = np.min(B_real)
    B_max = np.max(B_real)
    B_avg = np.average(B_real, weights=hist_real)

    idx_peak = np.argmax(hist)
    B_peak = B_mT[idx_peak]
    hist_peak = hist_norm[idx_peak]

    def B_to_kHz(B):
        return ((B - B_peak) * 1e-3 * gamma) / 1e3

    def weighted_percentile(values_in, weights, percentile):
        order = np.argsort(values_in)
        values_in = values_in[order]
        weights = weights[order]
        cumulative = np.cumsum(weights) / np.sum(weights)
        return np.interp(percentile / 100, cumulative, values_in)

    mask_fwhm = hist_norm >= 0.5
    B_left = B_mT[mask_fwhm][0]
    B_right = B_mT[mask_fwhm][-1]
    FWHM_mT = B_right - B_left
    FWHM_kHz = B_to_kHz(B_right) - B_to_kHz(B_left)

    P1, P5, P95, P99 = [weighted_percentile(B_mT, hist, p) for p in (1, 5, 95, 99)]

    ppm_p2p = (B_max - B_min) / B_avg * 1e6
    ppm_1 = (P99 - P1) / B_avg * 1e6
    ppm_5 = (P95 - P5) / B_avg * 1e6

    BW_p2p_Hz = (B_to_kHz(B_max) - B_to_kHz(B_min)) * 1e3
    BW_1_Hz = (B_to_kHz(P99) - B_to_kHz(P1)) * 1e3
    BW_5_Hz = (B_to_kHz(P95) - B_to_kHz(P5)) * 1e3

    fig_hist, ax = plt.subplots(figsize=(8, 5))
    bin_width = np.diff(edges)
    ax.bar(
        B_mT,
        hist_norm,
        width=bin_width * 0.92,
        align="center",
        color="white",
        edgecolor="grey",
        linewidth=1.2,
    )
    ax.set(xlabel="By (mT)", ylabel="Normalized histogram")
    ax.set_title(
        f"Magnet: {magnet_info}, FOV: {FOV_INFO}, Analysis: {analysis_info}\nBFOV Histogram (Normalized)",
        pad=30,
        fontstyle="italic",
    )

    for Bv in [B_min, B_avg, B_max]:
        ax.axvline(Bv, color=COL_MINMAX, linestyle=LS_MINMAX, linewidth=1)
        ax.text(
            Bv + 0.0005,
            0.75,
            f"{['Min', 'Avg', 'Max'][[B_min, B_avg, B_max].index(Bv)]}\n{Bv:.3f} mT\n{B_to_kHz(Bv):+.3f} kHz",
            fontsize=9,
            color=COL_MINMAX,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="lightcoral"),
        )

    ax.plot(B_peak, hist_peak, ".", color=COL_PEAK)
    ax.annotate(
        f"Peak {B_peak:.4f} mT ({B_to_kHz(B_peak):+.1f} kHz)",
        xy=(B_peak, hist_peak),
        xytext=(5, 0),
        textcoords="offset points",
        fontsize=9,
        color=COL_PEAK,
    )

    for value, label, color in [(P1, "P1", COL_P1), (P5, "P5", COL_P5), (P95, "P95", COL_P5), (P99, "P99", COL_P1)]:
        ax.axvline(value, color=color, linestyle=LS_PERCENT, linewidth=1)
        ax.text(
            value,
            0.05,
            f"{label}) {value:.3f} mT ({B_to_kHz(value):+.2f} kHz)",
            rotation=90,
            fontsize=8,
            color=color,
            ha="center",
            va="bottom",
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1.5),
        )

    ax.axhline(0.5, color="plum", linestyle="-.", linewidth=1)
    for value, label in [(B_left, "FWHM L"), (B_right, "FWHM R")]:
        ax.axvline(value, color=COLOR_FWHM, linestyle="-.", linewidth=1)
        ax.text(
            value,
            0.05,
            f"{label}) {value:.3f} mT ({B_to_kHz(value):+.2f} kHz)",
            rotation=90,
            fontsize=8,
            color=COLOR_FWHM,
            ha="center",
            va="bottom",
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1.5),
        )

    secax = ax.secondary_xaxis(
        "top",
        functions=(
            lambda B: B_to_kHz(B),
            lambda k: ((k * 1e3 / gamma) + B_peak * 1e-3) * 1e3,
        ),
    )
    secax.set_xlabel("Bandwidth (kHz)")

    inicio = 0.08
    espacio = 0.22
    metrics = [
        (inicio, f"P2P {ppm_p2p:.1f} ppm\n{BW_p2p_Hz:.1f} Hz", COL_MINMAX),
        (inicio + 1.2 * espacio, f"1-99% {ppm_1:.1f} ppm\n{BW_1_Hz:.1f} Hz", COL_P1),
        (inicio + 2.5 * espacio, f"5-95% {ppm_5:.1f} ppm\n{BW_5_Hz:.1f} Hz", COL_P5),
        (inicio + 3.7 * espacio, f"FWHM {FWHM_mT * 1000:.1f} uT\n{FWHM_kHz * 1000:.1f} Hz", COLOR_FWHM),
    ]
    ax.add_patch(
        plt.Rectangle(
            (min(x for x, _, _ in metrics) - 0.08, 1.13),
            max(x for x, _, _ in metrics) - min(x for x, _, _ in metrics) + 0.18,
            0.1,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor=COL_BOX_EDGE,
            clip_on=False,
        )
    )
    for x_pos, text, color in metrics:
        ax.text(x_pos, 1.17, text, transform=ax.transAxes, ha="center", va="center", fontsize=9, color=color, clip_on=False)

    ax.set_ylim(-0.05, 1.11)
    fig_hist.text(0.99, 0.01, datetime.now().strftime("%Y-%m-%d"), ha="right", va="bottom", fontsize=10, color="gray", alpha=0.8)
    plt.tight_layout()
    plt.savefig(histogram_png, dpi=300, bbox_inches="tight")
    plt.close(fig_hist)


def process_comsol_histogram(path):
    hist_path = Path(path).expanduser()
    if not hist_path.is_absolute():
        hist_path = Path.cwd() / hist_path
    if not hist_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {hist_path}")

    data = np.loadtxt(hist_path, comments="%")
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] < 2:
        raise ValueError(f"El TXT de histograma COMSOL debe tener al menos 2 columnas: {hist_path}")

    b_raw = data[:, 0]
    f_raw = data[:, 1]
    mask = np.isfinite(b_raw) & np.isfinite(f_raw)
    if not np.any(mask):
        raise ValueError("No hay bins/frecuencias finitas en el TXT de histograma COMSOL")

    b_raw = b_raw[mask]
    f_raw = f_raw[mask]
    order = np.argsort(b_raw)
    b_sorted = b_raw[order]
    f_sorted = f_raw[order]

    B_mT, inverse = np.unique(b_sorted, return_inverse=True)
    hist = np.zeros_like(B_mT, dtype=float)
    np.maximum.at(hist, inverse, f_sorted)

    if not np.any(hist > 0):
        raise ValueError("El histograma COMSOL no contiene frecuencias positivas")

    _, histogram_txt, histogram_norm_txt, histogram_png = _build_histogram_outputs(hist_path)
    magnet_info = MAGNET_INFO or hist_path.stem
    analysis_info = ANALYSIS or "COMSOL histogram input"

    if B_mT.size == 1:
        step = max(1e-12, abs(B_mT[0]) * 1e-6 + 1e-12)
        edges = np.array([B_mT[0] - step, B_mT[0] + step], dtype=float)
    else:
        mids = 0.5 * (B_mT[:-1] + B_mT[1:])
        left = B_mT[0] - 0.5 * (B_mT[1] - B_mT[0])
        right = B_mT[-1] + 0.5 * (B_mT[-1] - B_mT[-2])
        edges = np.concatenate(([left], mids, [right]))

    np.savetxt(histogram_txt, np.column_stack((B_mT, hist)), fmt="%.15g", delimiter="\t")

    if np.max(hist) > 0:
        hist_norm = hist / np.max(hist)
    else:
        hist_norm = np.zeros_like(hist)
    np.savetxt(histogram_norm_txt, np.column_stack((B_mT, hist_norm)), fmt="%.15g", delimiter="\t")

    gamma = 42.58e6

    COL_MINMAX = "red"
    COL_PEAK = "orchid"
    COLOR_FWHM = "magenta"
    COL_P1 = "royalblue"
    COL_P5 = "green"
    COL_BOX_EDGE = "grey"

    LS_MINMAX = ":"
    LS_PERCENT = "--"

    mask_hist = hist > 0
    B_real = B_mT[mask_hist]
    hist_real = hist[mask_hist]

    B_min = np.min(B_real)
    B_max = np.max(B_real)
    B_avg = np.average(B_real, weights=hist_real)

    idx_peak = np.argmax(hist)
    B_peak = B_mT[idx_peak]
    hist_peak = hist_norm[idx_peak]

    def B_to_kHz(B):
        return ((B - B_peak) * 1e-3 * gamma) / 1e3

    def weighted_percentile(values_in, weights, percentile):
        order = np.argsort(values_in)
        values_in = values_in[order]
        weights = weights[order]
        cumulative = np.cumsum(weights) / np.sum(weights)
        return np.interp(percentile / 100, cumulative, values_in)

    mask_fwhm = hist_norm >= 0.5
    B_left = B_mT[mask_fwhm][0]
    B_right = B_mT[mask_fwhm][-1]
    FWHM_mT = B_right - B_left
    FWHM_kHz = B_to_kHz(B_right) - B_to_kHz(B_left)

    P1, P5, P95, P99 = [weighted_percentile(B_mT, hist, p) for p in (1, 5, 95, 99)]

    ppm_p2p = (B_max - B_min) / B_avg * 1e6
    ppm_1 = (P99 - P1) / B_avg * 1e6
    ppm_5 = (P95 - P5) / B_avg * 1e6

    BW_p2p_Hz = (B_to_kHz(B_max) - B_to_kHz(B_min)) * 1e3
    BW_1_Hz = (B_to_kHz(P99) - B_to_kHz(P1)) * 1e3
    BW_5_Hz = (B_to_kHz(P95) - B_to_kHz(P5)) * 1e3

    fig_hist, ax = plt.subplots(figsize=(8, 5))
    bin_width = np.diff(edges)
    ax.bar(
        B_mT,
        hist_norm,
        width=bin_width * 0.92,
        align="center",
        color="white",
        edgecolor="grey",
        linewidth=1.2,
    )
    ax.set(xlabel="By (mT)", ylabel="Normalized histogram")
    ax.set_title(
        f"Magnet: {magnet_info}, FOV: {FOV_INFO}, Analysis: {analysis_info}\nBFOV Histogram (Normalized)",
        pad=30,
        fontstyle="italic",
    )

    for Bv in [B_min, B_avg, B_max]:
        ax.axvline(Bv, color=COL_MINMAX, linestyle=LS_MINMAX, linewidth=1)
        ax.text(
            Bv + 0.0005,
            0.75,
            f"{['Min', 'Avg', 'Max'][[B_min, B_avg, B_max].index(Bv)]}\n{Bv:.3f} mT\n{B_to_kHz(Bv):+.3f} kHz",
            fontsize=9,
            color=COL_MINMAX,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="lightcoral"),
        )

    ax.plot(B_peak, hist_peak, ".", color=COL_PEAK)
    ax.annotate(
        f"Peak {B_peak:.4f} mT ({B_to_kHz(B_peak):+.1f} kHz)",
        xy=(B_peak, hist_peak),
        xytext=(5, 0),
        textcoords="offset points",
        fontsize=9,
        color=COL_PEAK,
    )

    for value, label, color in [(P1, "P1", COL_P1), (P5, "P5", COL_P5), (P95, "P95", COL_P5), (P99, "P99", COL_P1)]:
        ax.axvline(value, color=color, linestyle=LS_PERCENT, linewidth=1)
        ax.text(
            value,
            0.05,
            f"{label}) {value:.3f} mT ({B_to_kHz(value):+.2f} kHz)",
            rotation=90,
            fontsize=8,
            color=color,
            ha="center",
            va="bottom",
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1.5),
        )

    ax.axhline(0.5, color="plum", linestyle="-.", linewidth=1)
    for value, label in [(B_left, "FWHM L"), (B_right, "FWHM R")]:
        ax.axvline(value, color=COLOR_FWHM, linestyle="-.", linewidth=1)
        ax.text(
            value,
            0.05,
            f"{label}) {value:.3f} mT ({B_to_kHz(value):+.2f} kHz)",
            rotation=90,
            fontsize=8,
            color=COLOR_FWHM,
            ha="center",
            va="bottom",
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1.5),
        )

    secax = ax.secondary_xaxis(
        "top",
        functions=(
            lambda B: B_to_kHz(B),
            lambda k: ((k * 1e3 / gamma) + B_peak * 1e-3) * 1e3,
        ),
    )
    secax.set_xlabel("Bandwidth (kHz)")

    inicio = 0.08
    espacio = 0.22
    metrics = [
        (inicio, f"P2P {ppm_p2p:.1f} ppm\n{BW_p2p_Hz:.1f} Hz", COL_MINMAX),
        (inicio + 1.2 * espacio, f"1-99% {ppm_1:.1f} ppm\n{BW_1_Hz:.1f} Hz", COL_P1),
        (inicio + 2.5 * espacio, f"5-95% {ppm_5:.1f} ppm\n{BW_5_Hz:.1f} Hz", COL_P5),
        (inicio + 3.7 * espacio, f"FWHM {FWHM_mT * 1000:.1f} uT\n{FWHM_kHz * 1000:.1f} Hz", COLOR_FWHM),
    ]
    ax.add_patch(
        plt.Rectangle(
            (min(x for x, _, _ in metrics) - 0.08, 1.13),
            max(x for x, _, _ in metrics) - min(x for x, _, _ in metrics) + 0.18,
            0.1,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor=COL_BOX_EDGE,
            clip_on=False,
        )
    )
    for x_pos, text, color in metrics:
        ax.text(x_pos, 1.17, text, transform=ax.transAxes, ha="center", va="center", fontsize=9, color=color, clip_on=False)

    ax.set_ylim(-0.05, 1.11)
    fig_hist.text(0.99, 0.01, datetime.now().strftime("%Y-%m-%d"), ha="right", va="bottom", fontsize=10, color="gray", alpha=0.8)
    plt.tight_layout()
    plt.savefig(histogram_png, dpi=300, bbox_inches="tight")
    plt.close(fig_hist)

    print(f"OK: {histogram_txt}")
    print(f"OK: {histogram_norm_txt}")
    print(f"OK: {histogram_png}")


def process_point_cloud():
    txt_path = Path(TXT_PATH).expanduser()
    if not txt_path.is_absolute():
        txt_path = Path.cwd() / txt_path
    if not txt_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {txt_path}")

    data = np.loadtxt(txt_path, comments="%")
    if data.ndim == 1:
        data = data.reshape(1, -1)

    cols = data.shape[1]
    for col in (X_COL, Y_COL, Z_COL, VALUE_COL):
        if col < 1 or col > cols:
            raise ValueError(f"La columna {col} no existe en {txt_path}. Columnas disponibles: 1..{cols}")

    x = data[:, X_COL - 1]
    y = data[:, Y_COL - 1]
    z = data[:, Z_COL - 1]
    values = data[:, VALUE_COL - 1]

    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z) & np.isfinite(values)
    if not np.any(mask):
        raise ValueError(f"No hay filas finitas para plotear en {txt_path}")

    x = x[mask]
    y = y[mask]
    z = z[mask]
    values = values[mask]

    stem, histogram_txt, histogram_norm_txt, histogram_png = _build_histogram_outputs(txt_path)
    magnet_info = MAGNET_INFO or stem
    analysis_info = ANALYSIS or f"Column {VALUE_COL} histogram ({BINS} bins)"

    output_png = Path(OUTPUT_PNG).expanduser() if OUTPUT_PNG else txt_path.with_suffix(".png")
    if not output_png.is_absolute():
        output_png = txt_path.parent / output_png

    _plot_and_save_histogram(values, histogram_txt, histogram_norm_txt, histogram_png, magnet_info, analysis_info)

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    sc = ax.scatter(
        y,
        x,
        z,
        c=values,
        cmap=CMAP,
        s=POINT_SIZE,
        depthshade=False,
        linewidths=0,
    )

    ax.set_title(TITLE)
    ax.set_xlabel(f"y ({AXIS_UNIT})")
    ax.set_ylabel(f"x ({AXIS_UNIT})")
    ax.set_zlabel(f"z ({AXIS_UNIT})")
    ax.view_init(elev=24, azim=-50)

    try:
        ax.set_box_aspect((np.ptp(y), np.ptp(x), np.ptp(z)))
    except Exception:
        pass

    cbar = fig.colorbar(sc, ax=ax, pad=0.08, shrink=0.8)
    cbar.set_label(VALUE_LABEL)

    fig.text(0.99, 0.01, datetime.now().strftime("%Y-%m-%d"), ha="right", va="bottom", fontsize=9, color="gray", alpha=0.8)
    plt.tight_layout()
    plt.savefig(output_png, dpi=300, bbox_inches="tight")

    if SHOW_PLOT:
        plt.show()
    else:
        plt.close(fig)

    print(f"OK: {output_png}")
    print(f"OK: {histogram_txt}")
    print(f"OK: {histogram_norm_txt}")
    print(f"OK: {histogram_png}")


def main():
    if COMSOL_TXT_HISTOGRAM:
        if not COMSOL_HISTOGRAM_PATH.strip():
            raise RuntimeError("COMSOL_HISTOGRAM_PATH esta vacio y COMSOL_TXT_HISTOGRAM=True")
        process_comsol_histogram(COMSOL_HISTOGRAM_PATH)
    else:
        process_point_cloud()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}")
