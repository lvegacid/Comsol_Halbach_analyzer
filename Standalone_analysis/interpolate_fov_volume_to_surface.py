from pathlib import Path
import re
from datetime import datetime

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import LinearNDInterpolator
from tkinter import Tk, filedialog

# Modo de entrada alternativo: usar TXT de histograma exportado por COMSOL
COMSOL_TXT_HISTOGRAM = False
COMSOL_HISTOGRAM_PATH = r""

# ============================================================
# CONFIGURACIÓN
# ============================================================
INPUT_TXT = r"Z:\Projects\Preclinico\Medidas\20260926 1805 Preclinico 10cm9cm_1cm 1000avg 200medidas_20260926_180547.txt"
# Histograma
#INPUT_TXT = r"Z:\Projects\Magnets\COMSOL_Simulation\Preclinico\Different_FOVs\N45SH\CylinderD100H100\Step5mm\B_coordinates_FromFile_Coordenadas_sensor_cilindro_D_0_100_L_0_100_step_0_005_cols_1_2_3.txt"
USE_FILE_DIALOG_IF_EMPTY = True

# Permite ejecutar analisis de superficie y volumen por separado o juntos
RUN_SURFACE_ANALYSIS = True
RUN_VOLUME_ANALYSIS = True
RUN_RAW_ANALYSIS = True


SHAPE = "sphere"  # "sphere" o "ellipsoid"

# Geometría - Esfera
R = 77.0/2  # mm

# Geometría - Elipsoide
A = 76/2  # mm
B = 78/2 # mm
C = 78/2  # mm

# Centro de la geometría (mm)
CENTER_X_MM = 0.0
CENTER_Y_MM = 0.0
CENTER_Z_MM = 0.0

# Número aproximado de puntos sobre la superficie
SURFACE_POINT_COUNT = 10000

# Selección de variable a interpolar (columna absoluta del TXT, 1-based)
# Ejemplo típico COMSOL: x y z Bx By Bz -> usar 4, 5 o 6
INTERPOLATE_COLUMN = 4
VALUE_LABEL = "By"    # Si está vacío, se infiere automáticamente
VALUE_UNIT = "mT"
# Fuerza sufijo de salida ("Bx", "By", "Bz", "normB"). Vacio => auto.
COMPONENT_SUFFIX_OVERRIDE = ""
MAGNET_INFO = ""
FOV_INFO = "Interpolated surface"
ANALYSIS = ""

# Estilo de gráficos
CMAP = "inferno"
MARKER_SIZE_3D = 250
MARKER_SIZE_2D = 150
ALPHA_2D = 0.9
SHUFFLE_2D_DRAW_ORDER = True
SURFACE_FIGSIZE = (9, 7)
HIST_FIGSIZE = (8, 5)
HIST_BINS = 100
VIEW_ELEV = 24
VIEW_AZIM = -50
INCLUDE_PLOTS_2D = True



# Muestreo volumetrico interno
VOLUME_POINT_COUNT = 80000
VOLUME_RANDOM_SEED = 42

# Export adicional: HTML 3D interactivo (girable con raton)
SAVE_INTERACTIVE_3D = True
OPEN_INTERACTIVE_3D = False
INTERACTIVE_MAX_POINTS = 50000
INTERACTIVE_MARKER_SIZE_DEFAULT = 3
INTERACTIVE_MARKER_SIZE_MIN = 1
INTERACTIVE_MARKER_SIZE_MAX = 20
INTERACTIVE_MARKER_SIZE_STEP = 1
INTERACTIVE_MARKER_OPACITY = 0.65

# Orientacion de ejes 3D (para replicar vista de referencia)
# SWAP_XY_3D=False => eje X muestra X real, eje Y muestra Y real
SWAP_XY_3D = True
# Signo de cada eje visualizado: 1 normal, -1 invertido
X_SIGN_3D = 1
Y_SIGN_3D = -1
Z_SIGN_3D = 1


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def pick_input_file(initial_dir=None):
    """Abre cuadro de diálogo para seleccionar el archivo TXT si no se especifica ruta."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title="Selecciona TXT exportado de COMSOL",
        initialdir=initial_dir or str(Path.cwd()),
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
    )
    root.destroy()
    return file_path


def is_float_token(token):
    try:
        float(token)
        return True
    except ValueError:
        return False


def guess_column_names(txt_path, n_cols):
    """Extrae nombres de columna desde comentarios con formato COMSOL (% header)."""
    best = None
    with txt_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.lstrip().startswith("%"):
                continue
            raw = line.lstrip()[1:].strip()
            if not raw:
                continue
            tokens = [t for t in re.split(r"[\s,;]+", raw) if t]
            if len(tokens) != n_cols:
                continue
            if all(not is_float_token(t) for t in tokens):
                best = tokens
    if best is not None:
        return best
    return [f"col_{i+1}" for i in range(n_cols)]


def build_surface(shape, point_count, center_mm, r, a, b, c):
    """Genera una superficie con distribución uniforme mediante espiral de Fibonacci."""
    cx, cy, cz = center_mm

    i = np.arange(0, point_count, dtype=float)
    phi = np.arccos(1 - 2 * (i + 0.5) / point_count)
    golden_ratio = (1 + np.sqrt(5)) / 2
    theta = 2 * np.pi * i / golden_ratio

    if shape == "sphere":
        x = cx + r * np.sin(phi) * np.cos(theta)
        y = cy + r * np.sin(phi) * np.sin(theta)
        z = cz + r * np.cos(phi)
        shape_desc = f"Sphere R={r:g} mm"
    elif shape == "ellipsoid":
        x = cx + a * np.sin(phi) * np.cos(theta)
        y = cy + b * np.sin(phi) * np.sin(theta)
        z = cz + c * np.cos(phi)
        shape_desc = f"Ellipsoid A={a:g} B={b:g} C={c:g} mm"
    else:
        raise ValueError("SHAPE debe ser 'sphere' o 'ellipsoid'.")

    return x, y, z, shape_desc


def build_volume(shape, point_count, center_mm, r, a, b, c, rng_seed):
    """Genera puntos aproximadamente uniformes dentro del volumen."""
    cx, cy, cz = center_mm
    rng = np.random.default_rng(int(rng_seed))

    # Direcciones uniformes en esfera unidad + radio con ley r^(1/3)
    dirs = rng.normal(size=(int(point_count), 3))
    norms = np.linalg.norm(dirs, axis=1)
    norms[norms == 0] = 1.0
    dirs = dirs / norms[:, None]
    rad = rng.random(int(point_count)) ** (1.0 / 3.0)

    if shape == "sphere":
        x = cx + r * rad * dirs[:, 0]
        y = cy + r * rad * dirs[:, 1]
        z = cz + r * rad * dirs[:, 2]
        shape_desc = f"Sphere R={r:g} mm"
    elif shape == "ellipsoid":
        x = cx + a * rad * dirs[:, 0]
        y = cy + b * rad * dirs[:, 1]
        z = cz + c * rad * dirs[:, 2]
        shape_desc = f"Ellipsoid A={a:g} B={b:g} C={c:g} mm"
    else:
        raise ValueError("SHAPE debe ser 'sphere' o 'ellipsoid'.")

    return x, y, z, shape_desc


def get_output_dir(parent_dir, shape, center_mm, r, a, b, c):
    """Genera la ruta de salida limpia sin superar límites de ruta de Windows."""
    cx, cy, cz = (f"{v:g}" for v in center_mm)
    if shape == "sphere":
        folder_name = f"Interpolated_Sphere_R_{r:g}_Center_{cx}_{cy}_{cz}"
    else:
        folder_name = f"Interpolated_Ellipsoid_A_{a:g}_B_{b:g}_C_{c:g}_Center_{cx}_{cy}_{cz}"
    
    return parent_dir / folder_name


def save_metrics(metrics_path, metrics):
    """Guarda las métricas en un archivo de texto simple."""
    lines = [f"{key}\t{val:.10g}" if isinstance(val, float) else f"{key}\t{val}" for key, val in metrics.items()]
    metrics_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_axis_sign(values, center_value, sign):
    return center_value + sign * (values - center_value)


def infer_output_component_suffix(value_label, column_name, override=""):
    ov = str(override).strip()
    if ov:
        ov_low = ov.lower()
        if ov_low in ("bx", "by", "bz", "normb", "bnorm"):
            return "normB" if ov_low in ("normb", "bnorm") else ov.capitalize()
        return re.sub(r"[^0-9A-Za-z]+", "", ov) or "value"

    text = f"{value_label} {column_name}".lower()
    if "bnorm" in text or "normb" in text or "b_norm" in text or "norm b" in text:
        return "normB"
    if re.search(r"(^|[^a-z])bx([^a-z]|$)", text):
        return "Bx"
    if re.search(r"(^|[^a-z])by([^a-z]|$)", text):
        return "By"
    if re.search(r"(^|[^a-z])bz([^a-z]|$)", text):
        return "Bz"
    return "value"


def save_interactive_3d_html(
    html_path,
    x_vals,
    y_vals,
    z_vals,
    value_vals,
    title,
    x_label,
    y_label,
    z_label,
    value_label,
    value_unit,
    max_points,
    marker_size_default,
    marker_size_min,
    marker_size_max,
    marker_size_step,
    open_in_browser,
):
    try:
        import plotly.graph_objects as go
    except Exception:
        print("AVISO: plotly no disponible. No se genera el HTML interactivo.")
        print("Instala con: pip install plotly")
        return False

    mask = np.isfinite(x_vals) & np.isfinite(y_vals) & np.isfinite(z_vals) & np.isfinite(value_vals)
    if not np.any(mask):
        print("AVISO: sin puntos validos para HTML interactivo.")
        return False

    x = x_vals[mask]
    y = y_vals[mask]
    z = z_vals[mask]
    v = value_vals[mask]

    if max_points and len(v) > max_points:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(v), size=max_points, replace=False)
        x = x[idx]
        y = y[idx]
        z = z[idx]
        v = v[idx]

    unit_suffix = f" ({value_unit})" if str(value_unit).strip() else ""
    marker_size_default = int(max(1, marker_size_default))
    marker_size_min = int(max(1, marker_size_min))
    marker_size_max = int(max(marker_size_min, marker_size_max))
    marker_size_step = int(max(1, marker_size_step))

    if marker_size_default < marker_size_min:
        marker_size_default = marker_size_min
    if marker_size_default > marker_size_max:
        marker_size_default = marker_size_max

    marker_opacity = float(np.clip(INTERACTIVE_MARKER_OPACITY, 0.05, 1.0))

    def padded_range(arr):
        vmin = float(np.min(arr))
        vmax = float(np.max(arr))
        span = vmax - vmin
        pad = max(1e-12, 0.03 * span) if span > 0 else 1e-6
        return [vmin - pad, vmax + pad]

    x_range = padded_range(x)
    y_range = padded_range(y)
    z_range = padded_range(z)

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                mode="markers",
                marker=dict(
                    size=marker_size_default,
                    color=v,
                    colorscale=CMAP,
                    showscale=True,
                    colorbar=dict(title=f"{value_label}{unit_suffix}"),
                    opacity=marker_opacity,
                ),
                hovertemplate=(
                    f"{x_label}: %{{x:.3f}}<br>"
                    f"{y_label}: %{{y:.3f}}<br>"
                    f"{z_label}: %{{z:.3f}}<br>"
                    f"{value_label}: %{{marker.color:.5g}}{unit_suffix}<extra></extra>"
                ),
            )
        ]
    )

    def make_camera(eye, up, projection_type):
        return dict(
            eye=eye,
            up=up,
            center=dict(x=0, y=0, z=0),
            projection=dict(type=projection_type),
        )

    camera_iso = make_camera(eye=dict(x=1.45, y=1.45, z=1.15), up=dict(x=0, y=0, z=1), projection_type="perspective")
    camera_x_up = make_camera(eye=dict(x=0.1, y=1.7, z=1.2), up=dict(x=1, y=0, z=0), projection_type="perspective")
    camera_y_up = make_camera(eye=dict(x=1.7, y=0.1, z=1.2), up=dict(x=0, y=1, z=0), projection_type="perspective")
    camera_z_up = make_camera(eye=dict(x=1.7, y=1.7, z=0.1), up=dict(x=0, y=0, z=1), projection_type="perspective")

    camera_xy = make_camera(eye=dict(x=0.0, y=0.0, z=2.2), up=dict(x=0, y=1, z=0), projection_type="orthographic")
    camera_xy_opposite = make_camera(eye=dict(x=0.0, y=0.0, z=-2.2), up=dict(x=0, y=1, z=0), projection_type="orthographic")
    camera_xz = make_camera(eye=dict(x=0.0, y=2.2, z=0.0), up=dict(x=0, y=0, z=1), projection_type="orthographic")
    camera_xz_opposite = make_camera(eye=dict(x=0.0, y=-2.2, z=0.0), up=dict(x=0, y=0, z=1), projection_type="orthographic")
    camera_yz = make_camera(eye=dict(x=2.2, y=0.0, z=0.0), up=dict(x=0, y=0, z=1), projection_type="orthographic")
    camera_yz_opposite = make_camera(eye=dict(x=-2.2, y=0.0, z=0.0), up=dict(x=0, y=0, z=1), projection_type="orthographic")

    fig.update_layout(
        title=title,
        scene=dict(
            xaxis=dict(title=x_label, range=x_range, autorange=False),
            yaxis=dict(title=y_label, range=y_range, autorange=False),
            zaxis=dict(title=z_label, range=z_range, autorange=False),
            aspectmode="cube",
            camera=camera_iso,
        ),
        dragmode="turntable",
        uirevision="keep",
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                x=0.01,
                y=1.12,
                xanchor="left",
                yanchor="top",
                showactive=True,
                buttons=[
                    {
                        "label": "3D isometrica",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_iso}],
                    },
                    {
                        "label": "3D X arriba",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_x_up}],
                    },
                    {
                        "label": "3D Y arriba",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_y_up}],
                    },
                    {
                        "label": "3D Z arriba",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_z_up}],
                    },
                    {
                        "label": "2D XY",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_xy}],
                    },
                    {
                        "label": "2D XY opuesto",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_xy_opposite}],
                    },
                    {
                        "label": "2D XZ",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_xz}],
                    },
                    {
                        "label": "2D XZ opuesto",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_xz_opposite}],
                    },
                    {
                        "label": "2D YZ",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_yz}],
                    },
                    {
                        "label": "2D YZ opuesto",
                        "method": "relayout",
                        "args": [{"scene.camera": camera_yz_opposite}],
                    },
                ],
            )
        ],
        sliders=[
            dict(
                active=max(0, (marker_size_default - marker_size_min) // marker_size_step),
                currentvalue={"prefix": "Marker size: "},
                pad={"t": 70},
                steps=[
                    {
                        "label": str(s),
                        "method": "restyle",
                        "args": [{"marker.size": s}, [0]],
                    }
                    for s in range(marker_size_min, marker_size_max + 1, marker_size_step)
                ],
            )
        ],
        margin=dict(l=0, r=0, t=110, b=0),
    )

    fig.write_html(str(html_path), include_plotlyjs="cdn", auto_open=bool(open_in_browser))
    return True


def save_bfov_histogram_outputs(
    b_values,
    hist_png,
    histogram_txt,
    histogram_norm_txt,
    magnet_info,
    analysis_info,
):
    gamma = 42.58e6

    COL_MINMAX = "red"
    COL_PEAK = "orchid"
    COLOR_FWHM = "magenta"
    COL_P1 = "royalblue"
    COL_P5 = "green"
    COL_BOX_EDGE = "grey"

    LS_MINMAX = ":"
    LS_PERCENT = "--"

    bins = max(1, int(HIST_BINS))
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
    std_w = np.sqrt(np.average((B_real - B_avg) ** 2, weights=hist_real))

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
        f"Magnet: {magnet_info}, FOV: {FOV_INFO}, Analysis: {analysis_info}\\nBFOV Histogram (Normalized)",
        pad=30,
        fontstyle="italic",
    )

    for Bv in [B_min, B_avg, B_max]:
        ax.axvline(Bv, color=COL_MINMAX, linestyle=LS_MINMAX, linewidth=1)
        ax.text(
            Bv + 0.0005,
            0.75,
            f"{['Min', 'Avg', 'Max'][[B_min, B_avg, B_max].index(Bv)]}\\n{Bv:.3f} mT\\n{B_to_kHz(Bv):+.3f} kHz",
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
    metrics_box = [
        (inicio, f"P2P {ppm_p2p:.1f} ppm\\n{BW_p2p_Hz:.1f} Hz", COL_MINMAX),
        (inicio + 1.2 * espacio, f"1-99% {ppm_1:.1f} ppm\\n{BW_1_Hz:.1f} Hz", COL_P1),
        (inicio + 2.5 * espacio, f"5-95% {ppm_5:.1f} ppm\\n{BW_5_Hz:.1f} Hz", COL_P5),
        (inicio + 3.7 * espacio, f"FWHM {FWHM_mT * 1000:.1f} uT\\n{FWHM_kHz * 1000:.1f} Hz", COLOR_FWHM),
    ]
    ax.add_patch(
        plt.Rectangle(
            (min(x for x, _, _ in metrics_box) - 0.08, 1.13),
            max(x for x, _, _ in metrics_box) - min(x for x, _, _ in metrics_box) + 0.18,
            0.1,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor=COL_BOX_EDGE,
            clip_on=False,
        )
    )
    for x_pos, text, color in metrics_box:
        ax.text(x_pos, 1.17, text, transform=ax.transAxes, ha="center", va="center", fontsize=9, color=color, clip_on=False)

    ax.set_ylim(-0.05, 1.11)
    fig_hist.text(0.99, 0.01, datetime.now().strftime("%Y-%m-%d"), ha="right", va="bottom", fontsize=10, color="gray", alpha=0.8)
    plt.tight_layout()
    plt.savefig(hist_png, dpi=300, bbox_inches="tight")
    plt.close(fig_hist)

    return {
        "N_valid": int(np.count_nonzero(mask_hist)),
        "N_nan": 0,
        "mean": float(B_avg),
        "std": float(std_w),
        "P1": float(P1),
        "P5": float(P5),
        "P95": float(P95),
        "P99": float(P99),
        "P2P": float(B_max - B_min),
        "min": float(B_min),
        "max": float(B_max),
    }


def process_comsol_histogram(path):
    hist_path = Path(path).expanduser()
    if not hist_path.is_absolute():
        hist_path = Path.cwd() / hist_path
    if not hist_path.exists():
        raise FileNotFoundError(f"No existe el archivo de histograma COMSOL: {hist_path}")

    data = np.loadtxt(hist_path, comments="%")
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] < 2:
        raise ValueError(f"El TXT de histograma COMSOL debe tener al menos 2 columnas: {hist_path}")

    b_raw = data[:, 0]
    f_raw = data[:, 1]
    mask = np.isfinite(b_raw) & np.isfinite(f_raw)
    if not np.any(mask):
        raise ValueError("No hay bins/frecuencias finitas en el histograma COMSOL")

    b_raw = b_raw[mask]
    f_raw = f_raw[mask]

    # COMSOL suele exportar puntos duplicados para dibujar escalones.
    # Se colapsa cada bin quedándose con su frecuencia maxima no nula.
    order = np.argsort(b_raw)
    b_sorted = b_raw[order]
    f_sorted = f_raw[order]

    B_mT, inverse = np.unique(b_sorted, return_inverse=True)
    hist = np.zeros_like(B_mT, dtype=float)
    np.maximum.at(hist, inverse, f_sorted)

    if B_mT.size == 1:
        step = max(1e-12, abs(B_mT[0]) * 1e-6 + 1e-12)
        edges = np.array([B_mT[0] - step, B_mT[0] + step], dtype=float)
    else:
        mids = 0.5 * (B_mT[:-1] + B_mT[1:])
        left = B_mT[0] - 0.5 * (B_mT[1] - B_mT[0])
        right = B_mT[-1] + 0.5 * (B_mT[-1] - B_mT[-2])
        edges = np.concatenate(([left], mids, [right]))

    component_suffix = infer_output_component_suffix(VALUE_LABEL.strip() or "By", VALUE_LABEL.strip() or "By", COMPONENT_SUFFIX_OVERRIDE)
    out_dir = hist_path.parent / f"{hist_path.stem}_processed_{component_suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    hist_png = out_dir / f"histogram_{component_suffix}.png"
    metrics_txt = out_dir / f"metrics_{component_suffix}.txt"
    histogram_txt = out_dir / f"BFOV_histogram_{component_suffix}.txt"
    histogram_norm_txt = out_dir / f"BFOV_histogram_normalized_{component_suffix}.txt"

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

    std_w = np.sqrt(np.average((B_real - B_avg) ** 2, weights=hist_real))

    idx_peak = np.argmax(hist)
    B_peak = B_mT[idx_peak]
    hist_peak = hist_norm[idx_peak]

    gamma = 42.58e6

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

    COL_MINMAX = "red"
    COL_PEAK = "orchid"
    COLOR_FWHM = "magenta"
    COL_P1 = "royalblue"
    COL_P5 = "green"
    COL_BOX_EDGE = "grey"
    LS_MINMAX = ":"
    LS_PERCENT = "--"

    magnet_info = MAGNET_INFO or hist_path.stem
    analysis_info = ANALYSIS or "COMSOL histogram input"

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
    metrics_box = [
        (inicio, f"P2P {ppm_p2p:.1f} ppm\n{BW_p2p_Hz:.1f} Hz", COL_MINMAX),
        (inicio + 1.2 * espacio, f"1-99% {ppm_1:.1f} ppm\n{BW_1_Hz:.1f} Hz", COL_P1),
        (inicio + 2.5 * espacio, f"5-95% {ppm_5:.1f} ppm\n{BW_5_Hz:.1f} Hz", COL_P5),
        (inicio + 3.7 * espacio, f"FWHM {FWHM_mT * 1000:.1f} uT\n{FWHM_kHz * 1000:.1f} Hz", COLOR_FWHM),
    ]
    ax.add_patch(
        plt.Rectangle(
            (min(x for x, _, _ in metrics_box) - 0.08, 1.13),
            max(x for x, _, _ in metrics_box) - min(x for x, _, _ in metrics_box) + 0.18,
            0.1,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor=COL_BOX_EDGE,
            clip_on=False,
        )
    )
    for x_pos, text, color in metrics_box:
        ax.text(x_pos, 1.17, text, transform=ax.transAxes, ha="center", va="center", fontsize=9, color=color, clip_on=False)

    ax.set_ylim(-0.05, 1.11)
    fig_hist.text(0.99, 0.01, datetime.now().strftime("%Y-%m-%d"), ha="right", va="bottom", fontsize=10, color="gray", alpha=0.8)
    plt.tight_layout()
    plt.savefig(hist_png, dpi=300, bbox_inches="tight")
    plt.close(fig_hist)

    metrics = {
        "N_valid": int(np.count_nonzero(mask_hist)),
        "N_nan": 0,
        "mean": float(B_avg),
        "std": float(std_w),
        "P1": float(P1),
        "P5": float(P5),
        "P95": float(P95),
        "P99": float(P99),
        "P2P": float(B_max - B_min),
        "min": float(B_min),
        "max": float(B_max),
    }
    save_metrics(metrics_txt, metrics)

    print("\nModo COMSOL histogram completado:")
    print(f" -> Directorio: {out_dir}")
    print(f" -> {hist_png.name}")
    print(f" -> {metrics_txt.name}")
    print(f" -> {histogram_txt.name}")
    print(f" -> {histogram_norm_txt.name}")


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

def process_point_cloud():
    mpl.rcParams.update(mpl.rcParamsDefault)
    plt.style.use("default")

    # 1. Obtención y validación del archivo de entrada
    txt_path_str = INPUT_TXT.strip()
    if not txt_path_str and USE_FILE_DIALOG_IF_EMPTY:
        txt_path_str = pick_input_file()

    if not txt_path_str:
        raise RuntimeError("No se especificó ningún archivo de entrada.")

    txt_path = Path(txt_path_str).expanduser()
    if not txt_path.is_absolute():
        txt_path = Path.cwd() / txt_path
    if not txt_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {txt_path}")

    # 2. Carga y parseo de datos
    data = np.loadtxt(txt_path, comments="%")
    if data.ndim == 1:
        data = data.reshape(1, -1)

    n_cols = data.shape[1]
    if n_cols < 4:
        raise ValueError(f"Se esperan al menos 4 columnas [x, y, z, var], halladas: {n_cols}")

    col_names = guess_column_names(txt_path, n_cols)
    xyz_m = data[:, :3]

    # Selección de columna de datos
    col_idx = int(INTERPOLATE_COLUMN) - 1
    if not (3 <= col_idx < n_cols):
        raise ValueError(
            f"INTERPOLATE_COLUMN={INTERPOLATE_COLUMN} fuera de rango. "
            f"Debe estar entre 4 y {n_cols} para columnas de variable."
        )

    values = data[:, col_idx]
    value_label = VALUE_LABEL.strip() or col_names[col_idx]
    component_suffix = infer_output_component_suffix(value_label, col_names[col_idx], COMPONENT_SUFFIX_OVERRIDE)
    print(f"Columna seleccionada para interpolar: {col_idx + 1} ({value_label})")
    print(f"Sufijo de componente para salidas: {component_suffix}")

    # Filtrar valores infinitos/NaN del origen
    base_mask = np.isfinite(xyz_m).all(axis=1) & np.isfinite(values)
    if not np.any(base_mask):
        raise ValueError("No hay datos válidos para interpolar.")

    xyz_valid_m = xyz_m[base_mask]
    xyz_mm = xyz_valid_m * 1000.0  # Convertir m a mm
    values = values[base_mask]

    # 3. Creación de superficie de interpolación
    shape = SHAPE.strip().lower()
    center_mm = (CENTER_X_MM, CENTER_Y_MM, CENTER_Z_MM)

    x_surf, y_surf, z_surf, shape_desc = build_surface(
        shape=shape,
        point_count=int(SURFACE_POINT_COUNT),
        center_mm=center_mm,
        r=float(R),
        a=float(A),
        b=float(B),
        c=float(C),
    )

    # 4. Interpolación 3D dentro de las geometrías solicitadas
    interpolator = LinearNDInterpolator(xyz_mm, values, fill_value=np.nan)

    # 5. Configuración de directorio de salida corto y limpio
    out_dir = get_output_dir(txt_path.parent, shape, center_mm, R, A, B, C)
    out_dir.mkdir(parents=True, exist_ok=True)

    def run_spatial_analysis(
        kind,
        x_geom,
        y_geom,
        z_geom,
        title_target,
        vals_flat_source=None,
        source_coord_unit="mm",
        analysis_dir=None,
        title_prefix="Interpolated",
        include_center_text=True,
    ):
        if vals_flat_source is None:
            vals_grid = interpolator(x_geom, y_geom, z_geom)
            vals_flat = np.ravel(vals_grid)
        else:
            vals_flat = np.ravel(vals_flat_source)

        valid_mask = np.isfinite(vals_flat)
        n_total = vals_flat.size
        n_valid = int(np.count_nonzero(valid_mask))
        n_nan = n_total - n_valid

        print(f"Puntos {kind} totales: {n_total}")
        print(f"Puntos válidos interpolados ({kind}): {n_valid}")
        print(f"Puntos fuera del dominio (NaN) ({kind}): {n_nan}")

        if n_valid == 0:
            print(f"AVISO: sin puntos validos para {kind}. Se omite este analisis.")
            return

        valid_values = vals_flat[valid_mask]

        kind_suffix = "Raw" if kind == "raw" else kind
        suffix = f"_{kind_suffix}_{component_suffix}"
        out_base_dir = analysis_dir if analysis_dir is not None else out_dir
        out_base_dir.mkdir(parents=True, exist_ok=True)

        spatial_png_name = f"surface_2Dviews{suffix}.png" if INCLUDE_PLOTS_2D else f"surface{suffix}.png"
        spatial_png = out_base_dir / spatial_png_name
        spatial_html = out_base_dir / f"surface_interactive{suffix}.html"
        hist_png = out_base_dir / f"histogram{suffix}.png"
        interpolated_txt = out_base_dir / f"interpolated{suffix}.txt"
        metrics_txt = out_base_dir / f"metrics{suffix}.txt"
        histogram_txt = out_base_dir / f"BFOV_histogram{suffix}.txt"
        histogram_norm_txt = out_base_dir / f"BFOV_histogram_normalized{suffix}.txt"

        coord_header = source_coord_unit.lower()

        out_matrix = np.column_stack((x_geom, y_geom, z_geom, vals_flat))
        np.savetxt(
            interpolated_txt,
            out_matrix,
            fmt="%.9g",
            header=f"x_{coord_header}\ty_{coord_header}\tz_{coord_header}\tvalue",
            comments="",
            delimiter="\t",
        )

        metrics = {
            "N_valid": n_valid,
            "N_nan": n_nan,
            "mean": float(np.mean(valid_values)),
            "std": float(np.std(valid_values, ddof=0)),
            "P1": float(np.percentile(valid_values, 1)),
            "P5": float(np.percentile(valid_values, 5)),
            "P95": float(np.percentile(valid_values, 95)),
            "P99": float(np.percentile(valid_values, 99)),
            "P2P": float(np.ptp(valid_values)),
            "min": float(np.min(valid_values)),
            "max": float(np.max(valid_values)),
        }
        save_metrics(metrics_txt, metrics)

        norm = mpl.colors.Normalize(vmin=metrics["min"], vmax=metrics["max"])

        if source_coord_unit.lower() == "m":
            center_x = CENTER_X_MM / 1000.0
            center_y = CENTER_Y_MM / 1000.0
            center_z = CENTER_Z_MM / 1000.0
            axis_unit = "m"
        else:
            center_x = CENTER_X_MM
            center_y = CENTER_Y_MM
            center_z = CENTER_Z_MM
            axis_unit = "mm"

        x_plot = apply_axis_sign(x_geom, center_x, X_SIGN_3D)
        y_plot = apply_axis_sign(y_geom, center_y, Y_SIGN_3D)
        z_plot = apply_axis_sign(z_geom, center_z, Z_SIGN_3D)

        if SWAP_XY_3D:
            x_disp = y_plot
            y_disp = x_plot
            x_label = f"Y ({axis_unit})"
            y_label = f"X ({axis_unit})"
        else:
            x_disp = x_plot
            y_disp = y_plot
            x_label = f"X ({axis_unit})"
            y_label = f"Y ({axis_unit})"

        x_flat = np.ravel(x_disp)
        y_flat = np.ravel(y_disp)
        z_flat = np.ravel(z_plot)

        if INCLUDE_PLOTS_2D:
            fig = plt.figure(figsize=(18, 9.2))
            ax = fig.add_subplot(2, 4, 1, projection="3d")
            ax_xy = fig.add_subplot(2, 4, 2)
            ax_yz = fig.add_subplot(2, 4, 3)
            ax_xz = fig.add_subplot(2, 4, 4)
            ax_3d_back = fig.add_subplot(2, 4, 5, projection="3d")
            ax_xy_back = fig.add_subplot(2, 4, 6)
            ax_yz_back = fig.add_subplot(2, 4, 7)
            ax_xz_back = fig.add_subplot(2, 4, 8)
        else:
            fig = plt.figure(figsize=SURFACE_FIGSIZE)
            ax = fig.add_subplot(111, projection="3d")

        sc = ax.scatter(
            x_flat,
            y_flat,
            z_flat,
            c=vals_flat,
            cmap=CMAP,
            norm=norm,
            s=MARKER_SIZE_3D,
            alpha=0.8,
            linewidth=0,
        )

        valid_indices = np.flatnonzero(valid_mask)
        min_idx = valid_indices[int(np.argmin(valid_values))]
        max_idx = valid_indices[int(np.argmax(valid_values))]

        unit_suffix = f" ({VALUE_UNIT})" if VALUE_UNIT.strip() else ""

        ax.scatter(
            [x_flat[min_idx], x_flat[max_idx]],
            [y_flat[min_idx], y_flat[max_idx]],
            [z_flat[min_idx], z_flat[max_idx]],
            c=["black", "white"],
            s=max(20, MARKER_SIZE_3D * 3),
            edgecolors=["white", "black"],
            linewidths=0.8,
            depthshade=False,
            zorder=5,
        )

        ax.text(
            x_flat[min_idx],
            y_flat[min_idx],
            z_flat[min_idx],
            f"min: {metrics['min']:.4g}{unit_suffix}",
            fontsize=9,
            color="black",
            zorder=6,
        )
        ax.text(
            x_flat[max_idx],
            y_flat[max_idx],
            z_flat[max_idx],
            f"max: {metrics['max']:.4g}{unit_suffix}",
            fontsize=9,
            color="black",
            zorder=6,
        )

        if include_center_text:
            center_text = f"Center=({CENTER_X_MM:g}, {CENTER_Y_MM:g}, {CENTER_Z_MM:g}) mm"
            ax.set_title(f"{title_prefix} {value_label} on {title_target}\n{center_text}")
        else:
            ax.set_title(f"{title_prefix} {value_label} on {title_target}")
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_zlabel(f"Z ({axis_unit})")
        ax.view_init(elev=VIEW_ELEV, azim=VIEW_AZIM)

        print(
            "Orientacion 3D: "
            f"SWAP_XY_3D={SWAP_XY_3D}, X_SIGN_3D={X_SIGN_3D}, "
            f"Y_SIGN_3D={Y_SIGN_3D}, Z_SIGN_3D={Z_SIGN_3D}"
        )

        try:
            ax.set_box_aspect((np.ptp(x_disp), np.ptp(y_disp), np.ptp(z_plot)))
        except Exception:
            pass

        if INCLUDE_PLOTS_2D:
            def set_opposite_2d_view(axis):
                axis.invert_xaxis()
                axis.invert_yaxis()

            if SHUFFLE_2D_DRAW_ORDER:
                idx_2d = np.random.default_rng(42).permutation(len(vals_flat))
                x2 = x_flat[idx_2d]
                y2 = y_flat[idx_2d]
                z2 = z_flat[idx_2d]
                v2 = vals_flat[idx_2d]
            else:
                x2 = x_flat
                y2 = y_flat
                z2 = z_flat
                v2 = vals_flat

            xy = ax_xy.scatter(x2, y2, c=v2, cmap=CMAP, norm=norm, s=max(1, MARKER_SIZE_2D), alpha=ALPHA_2D, linewidths=0, edgecolors="none")
            ax_yz.scatter(y2, z2, c=v2, cmap=CMAP, norm=norm, s=max(1, MARKER_SIZE_2D), alpha=ALPHA_2D, linewidths=0, edgecolors="none")
            ax_xz.scatter(x2, z2, c=v2, cmap=CMAP, norm=norm, s=max(1, MARKER_SIZE_2D), alpha=ALPHA_2D, linewidths=0, edgecolors="none")

            ax_3d_back.scatter(
                x_flat,
                y_flat,
                z_flat,
                c=vals_flat,
                cmap=CMAP,
                norm=norm,
                s=MARKER_SIZE_3D,
                alpha=0.8,
                linewidth=0,
            )
            ax_3d_back.view_init(elev=-VIEW_ELEV, azim=VIEW_AZIM + 180)
            ax_3d_back.set_title("-3D")
            ax_3d_back.set_xlabel(x_label)
            ax_3d_back.set_ylabel(y_label)
            ax_3d_back.set_zlabel(f"Z ({axis_unit})")
            try:
                ax_3d_back.set_box_aspect((np.ptp(x_disp), np.ptp(y_disp), np.ptp(z_plot)))
            except Exception:
                pass

            xy_back = ax_xy_back.scatter(x2, y2, c=v2, cmap=CMAP, norm=norm, s=max(1, MARKER_SIZE_2D), alpha=ALPHA_2D, linewidths=0, edgecolors="none")
            ax_yz_back.scatter(y2, z2, c=v2, cmap=CMAP, norm=norm, s=max(1, MARKER_SIZE_2D), alpha=ALPHA_2D, linewidths=0, edgecolors="none")
            ax_xz_back.scatter(x2, z2, c=v2, cmap=CMAP, norm=norm, s=max(1, MARKER_SIZE_2D), alpha=ALPHA_2D, linewidths=0, edgecolors="none")

            ax_xy.set_title("XY")
            ax_xy.set_xlabel(x_label)
            ax_xy.set_ylabel(y_label)
            ax_xy.set_aspect("equal", adjustable="box")

            ax_yz.set_title("YZ")
            ax_yz.set_xlabel(y_label)
            ax_yz.set_ylabel(f"Z ({axis_unit})")
            ax_yz.set_aspect("equal", adjustable="box")

            ax_xz.set_title("XZ")
            ax_xz.set_xlabel(x_label)
            ax_xz.set_ylabel(f"Z ({axis_unit})")
            ax_xz.set_aspect("equal", adjustable="box")

            ax_xy_back.set_title("-XY")
            ax_xy_back.set_xlabel(x_label)
            ax_xy_back.set_ylabel(y_label)
            ax_xy_back.set_aspect("equal", adjustable="box")
            set_opposite_2d_view(ax_xy_back)

            ax_yz_back.set_title("-YZ")
            ax_yz_back.set_xlabel(y_label)
            ax_yz_back.set_ylabel(f"Z ({axis_unit})")
            ax_yz_back.set_aspect("equal", adjustable="box")
            set_opposite_2d_view(ax_yz_back)

            ax_xz_back.set_title("-XZ")
            ax_xz_back.set_xlabel(x_label)
            ax_xz_back.set_ylabel(f"Z ({axis_unit})")
            ax_xz_back.set_aspect("equal", adjustable="box")
            set_opposite_2d_view(ax_xz_back)

            fig.subplots_adjust(left=0.04, right=0.88, bottom=0.06, top=0.93, wspace=0.30, hspace=0.28)
            cbar = fig.colorbar(sc, ax=fig.axes, shrink=0.92, pad=0.02)
        else:
            cbar = fig.colorbar(sc, ax=ax, shrink=0.75, pad=0.08)

        cbar.set_label(f"{value_label}{unit_suffix}")

        if not INCLUDE_PLOTS_2D:
            plt.tight_layout()
        fig.savefig(spatial_png, dpi=300, bbox_inches="tight")
        plt.close(fig)

        if SAVE_INTERACTIVE_3D:
            save_interactive_3d_html(
                html_path=spatial_html,
                x_vals=x_flat,
                y_vals=y_flat,
                z_vals=z_flat,
                value_vals=vals_flat,
                title=f"Interpolated {value_label} on {title_target}",
                x_label=x_label,
                y_label=y_label,
                z_label=f"Z ({axis_unit})",
                value_label=value_label,
                value_unit=VALUE_UNIT,
                max_points=int(INTERACTIVE_MAX_POINTS),
                marker_size_default=int(INTERACTIVE_MARKER_SIZE_DEFAULT),
                marker_size_min=int(INTERACTIVE_MARKER_SIZE_MIN),
                marker_size_max=int(INTERACTIVE_MARKER_SIZE_MAX),
                marker_size_step=int(INTERACTIVE_MARKER_SIZE_STEP),
                open_in_browser=OPEN_INTERACTIVE_3D,
            )

        magnet_info = MAGNET_INFO or txt_path.stem
        if kind == "raw":
            analysis_info = ANALYSIS or f"Raw column {INTERPOLATE_COLUMN} histogram ({HIST_BINS} bins)"
        else:
            analysis_info = ANALYSIS or f"Column {INTERPOLATE_COLUMN} histogram ({HIST_BINS} bins)"
        save_bfov_histogram_outputs(
            b_values=valid_values,
            hist_png=hist_png,
            histogram_txt=histogram_txt,
            histogram_norm_txt=histogram_norm_txt,
            magnet_info=magnet_info,
            analysis_info=analysis_info,
        )

        print(f"\nArchivos generados exitosamente ({kind}) en:")
        print(f" -> Directorio: {out_base_dir}")
        print(f" -> {spatial_png.name}")
        if SAVE_INTERACTIVE_3D:
            print(f" -> {spatial_html.name}")
        print(f" -> {hist_png.name}")
        print(f" -> {interpolated_txt.name}")
        print(f" -> {metrics_txt.name}")
        print(f" -> {histogram_txt.name}")
        print(f" -> {histogram_norm_txt.name}")

    if RUN_SURFACE_ANALYSIS:
        run_spatial_analysis("surface", x_surf, y_surf, z_surf, shape_desc)

    if RUN_VOLUME_ANALYSIS:
        x_vol, y_vol, z_vol, shape_desc_vol = build_volume(
            shape=shape,
            point_count=int(VOLUME_POINT_COUNT),
            center_mm=center_mm,
            r=float(R),
            a=float(A),
            b=float(B),
            c=float(C),
            rng_seed=int(VOLUME_RANDOM_SEED),
        )
        run_spatial_analysis("volume", x_vol, y_vol, z_vol, shape_desc_vol)

    if RUN_RAW_ANALYSIS:
        raw_dir = out_dir / "Raw"
        run_spatial_analysis(
            kind="raw",
            x_geom=xyz_valid_m[:, 0],
            y_geom=xyz_valid_m[:, 1],
            z_geom=xyz_valid_m[:, 2],
            title_target="Original points",
            vals_flat_source=values,
            source_coord_unit="m",
            analysis_dir=raw_dir,
            title_prefix="Raw",
            include_center_text=False,
        )

    if not RUN_SURFACE_ANALYSIS and not RUN_VOLUME_ANALYSIS and not RUN_RAW_ANALYSIS:
        raise RuntimeError("Activa RUN_SURFACE_ANALYSIS, RUN_VOLUME_ANALYSIS y/o RUN_RAW_ANALYSIS.")


def main():
    mpl.rcParams.update(mpl.rcParamsDefault)
    plt.style.use("default")

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