import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib as mpl
import argparse
import os
import sys
mpl.rcParams.update(mpl.rcParamsDefault)
plt.style.use("default")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['font.size'] = 10
# ============================================================
# CONFIGURACIÓN GLOBAL (TODO editable aquí)
# ============================================================

#file_path = r"Z:\Projects\Preclinico\Halbach\Discarded\142mT\BFOV_histogram_nonlinear_discrete_142mT.txt"
file_path = r"Z:\Projects\Kepler\Halbach\50mT_237ppm_zigzag_HalfCubeAlternated\Shimming\BFOV_Kepler_50mT_halfzigzag_flat_shimming_nonlinear.txt"

# --- INFO DEL CASO ---
Magnet_info = "Kepler,mT,zigzag,nonlinear N48 with linear shimming"
FOV_info    = "Sphere(340 mm)"
    #"Ellipsoid(75x78x78 mm)"
    #"Ellipsoid(340x340x200 mm)"
Analysis    =  "Nonlinear/B_r=1.38T/H_c=-868kA/m"#"Flat/B_r=1.4T"#"Nonlinear/B_r=1.38T/H_c=-868kA/m" #/mu_r=1.05"#"Nonlinear/B_r=1.4T/H_c=-868kA/m"# "Nonlinear/B_r=1.32T/H_c=-1592kA/m"# "Linear/B_r=1.32T/mu_r=1.05" #"Nonlinear/B_r=1.32T/H_c=-1592kA/m"# 
#"Nonlinear/B_r=1.4T/H_c=-868kA/m"


def parse_args():
    parser = argparse.ArgumentParser(description="BFOV histogram plot postprocess")
    parser.add_argument("--file-path", dest="file_path", help="Ruta al TXT BFOV")
    parser.add_argument("--file-path-m", dest="file_path_m", help="Ruta al TXT Magnets histogram")
    parser.add_argument("--magnet-info", dest="magnet_info", help="Texto Magnet_info")
    parser.add_argument("--fov-info", dest="fov_info", help="Texto FOV_info")
    parser.add_argument("--analysis", dest="analysis", help="Texto Analysis")
    parser.add_argument("--output-png", dest="output_png", help="Ruta PNG de salida")
    parser.add_argument("--output-png-m", dest="output_png_m", help="Ruta PNG de salida para Magnets")
    parser.add_argument("--br", dest="br", type=float, help="Br en Tesla para Magnets")
    parser.add_argument("--step-percent", dest="step_percent", type=float, help="Paso porcentual para bins de Magnets")
    parser.add_argument("--same-name-png", action="store_true", help="Guardar como <txt>.png")
    parser.add_argument("--bfov-only", action="store_true", help="Solo ejecutar bloque BFOV")
    parser.add_argument("--magnets-only", action="store_true", help="Solo ejecutar bloque Magnets")
    parser.add_argument("--no-show", action="store_true", help="No abrir ventanas de plot")
    return parser.parse_args()


args = parse_args()

if args.file_path:
    file_path = args.file_path
if args.file_path_m:
    file_path_M = args.file_path_m
if args.magnet_info:
    Magnet_info = args.magnet_info
if args.fov_info:
    FOV_info = args.fov_info
if args.analysis:
    Analysis = args.analysis

if args.no_show:
    try:
        plt.switch_backend("Agg")
    except Exception:
        pass
    plt.ioff()

if args.magnets_only:
    args.bfov_only = True


gamma = 42.58e6  # Hz/T

# --- COLORES ---
COL_MINMAX = "red"
COL_PEAK   = "orchid"
COLOR_FWHM  =  "magenta"
COL_P1     = "royalblue"
COL_P5     = "green"
COL_BOX_EDGE = "grey"

# --- ESTILOS ---
LS_MINMAX = ":"
LS_PERCENT = "--"

# ============================================================
# LECTURA
# ============================================================

data = np.loadtxt(file_path, comments='%')
B_mT, hist = data[:,0], data[:,1]
hist_norm = hist / np.max(hist)

# ============================================================
# MÉTRICAS FÍSICAS
# ============================================================

mask = hist > 0
B_real, hist_real = B_mT[mask], hist[mask]

B_min, B_max = np.min(B_real), np.max(B_real)
B_avg = np.average(B_real, weights=hist_real)

idx_peak = np.argmax(hist)
B_peak, hist_peak = B_mT[idx_peak], hist_norm[idx_peak]



# ============================================================
# FUNCIONES
# ============================================================

def B_to_kHz(B): return ((B - B_peak)*1e-3*gamma)/1e3

def weighted_percentile(v,w,p):
    s = np.argsort(v)
    v,w = v[s], w[s]
    c = np.cumsum(w)/np.sum(w)
    return np.interp(p/100, c, v)

# ============================================================
# FWHM
# ============================================================

half_max = 0.5

mask_fwhm = hist_norm >= half_max

B_left  = B_mT[mask_fwhm][0]
B_right = B_mT[mask_fwhm][-1]

FWHM_mT  = B_right - B_left
FWHM_kHz = B_to_kHz(B_right) - B_to_kHz(B_left)



# ============================================================
# PERCENTILES
# ============================================================

P1, P5, P95, P99 = [weighted_percentile(B_mT,hist,p) for p in (1,5,95,99)]

# ============================================================
# ppm
# ============================================================

ppm_p2p = (B_max-B_min)/B_avg*1e6
ppm_1   = (P99-P1)/B_avg*1e6
ppm_5   = (P95-P5)/B_avg*1e6
# --- Bandwidths en Hz (referenciados al peak) ---
BW_p2p_Hz = (B_to_kHz(B_max) - B_to_kHz(B_min)) * 1e3
BW_1_Hz   = (B_to_kHz(P99) - B_to_kHz(P1)) * 1e3
BW_5_Hz   = (B_to_kHz(P95) - B_to_kHz(P5)) * 1e3

# ============================================================
# PLOT
# ============================================================

fig, ax = plt.subplots(figsize=(8,5))
ax.plot(B_mT, hist_norm, color="grey")
ax.set(xlabel="By (mT)", ylabel="Normalized histogram")
case_title = f"Magnet: {Magnet_info}, FOV: {FOV_info}, Analysis: {Analysis}"
ax.set_title(
    case_title + "\n" + "BFOV Histogram (Normalized)",
    pad=30,
    fontstyle='italic'
)

# --- Min / Avg / Max ---
for Bv in [B_min, B_avg, B_max]:
    ax.axvline(Bv, color=COL_MINMAX, linestyle=LS_MINMAX, linewidth=1)
    ax.text(Bv+0.0005,0.75,
        f"{['Min','Avg','Max'][[B_min,B_avg,B_max].index(Bv)]}\n"
        f"{Bv:.3f} mT\n{B_to_kHz(Bv):+.3f} kHz",
        fontsize=9, color=COL_MINMAX,
        bbox=dict(facecolor='white', alpha=0.8, edgecolor='lightcoral'))


# --- Pico ---
ax.plot(B_peak, hist_peak,'.',color=COL_PEAK)
ax.annotate(f"Peak {B_peak:.4f} mT ({B_to_kHz(B_peak):+.1f} kHz)",xy=(B_peak,hist_peak),
            xytext=(5,0),textcoords='offset points',
            fontsize=9,color=COL_PEAK)

# --- Percentiles ---
for val,lab,col in [(P1,"P1",COL_P1),(P5,"P5",COL_P5),
                    (P95,"P95",COL_P5),(P99,"P99",COL_P1)]:
    ax.axvline(val,color=col,linestyle=LS_PERCENT,linewidth=1)
    ax.text(val,0.05,
            f"{lab}) {val:.3f} mT ({B_to_kHz(val):+.2f} kHz)",
            rotation=90,fontsize=8,color=col,ha='center', va='bottom', 
            bbox=dict(facecolor='white',alpha=0.8,edgecolor='none',pad=1.5))

# --- FWHM  ---
ax.axhline(0.5, color="plum", linestyle='-.', linewidth=1)
for val, lab in [(B_left, "FWHM L"), (B_right, "FWHM R")]:
    ax.axvline(val, color=COLOR_FWHM, linestyle='-.', linewidth=1)
    ax.text(val, 0.05, f"{lab}) {val:.3f} mT ({B_to_kHz(val):+.2f} kHz)",
            rotation=90, fontsize=8, color=COLOR_FWHM, ha='center', va='bottom', bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1.5))

# --- Eje secundario ---
secax = ax.secondary_xaxis('top',
    functions=(lambda B: B_to_kHz(B),
               lambda k: ((k*1e3/gamma)+B_peak*1e-3)*1e3))
secax.set_xlabel("Bandwidth (kHz)")

# --- Panel ppm DEBAJO DEL TÍTULO ---
inicio = 0.08
espacio =0.22
metrics = [
    (inicio, f"P2P {ppm_p2p:.1f} ppm\n{BW_p2p_Hz:.1f} Hz", COL_MINMAX),
    (inicio+1.2*espacio, f"1–99% {ppm_1:.1f} ppm\n{BW_1_Hz:.1f} Hz", COL_P1),
    (inicio+2.5*espacio, f"5–95% {ppm_5:.1f} ppm\n{BW_5_Hz:.1f} Hz", COL_P5),
    (inicio+3.7*espacio, f"FWHM {FWHM_mT*1000:.1f} uT\n{FWHM_kHz*1000:.1f} Hz", COLOR_FWHM)
]
y_text = 1.17

# Recuadro automático
ax.add_patch(plt.Rectangle(
    (min(x for x,_,_ in metrics)-0.08, y_text-0.04),
    (max(x for x,_,_ in metrics)-min(x for x,_,_ in metrics)+0.18),
    0.1,
    transform=ax.transAxes,
    facecolor='white',
    edgecolor=COL_BOX_EDGE,
    clip_on=False))

# Textos
for x, text, col in metrics:
    ax.text(x, y_text, text,
            transform=ax.transAxes,
            ha='center', va='center',
            fontsize=9, color=col,
            clip_on=False)



ax.set_ylim(-0.05,1.11)


# --- Fecha fuera del plot (esquina inferior derecha de la figura) ---
fecha = datetime.now().strftime("%Y-%m-%d")

fig.text(0.99, 0.01, fecha,
         ha='right', va='bottom',
         fontsize=10,
         color='gray',
         alpha=0.8)

plt.tight_layout()
if args.output_png:
    output_path_bfov = args.output_png
elif args.same_name_png:
    output_path_bfov = os.path.splitext(file_path)[0] + ".png"
else:
    output_path_bfov = file_path.replace(".txt","_BFOV.png")

plt.savefig(output_path_bfov, dpi=300, bbox_inches='tight')
if not args.no_show:
    plt.show()

if args.bfov_only:
    sys.exit(0)




# ============================================================
#%% ANÁLISIS DEL HISTOGRAMA DE DEMAGNETIZACIÓN: Magnetización relativa M/Br (%)
# ============================================================

#file_path_M = r"Z:\Projects\PhysioII - NextMRI\Magnet\Linear_COMSOL_analysis\Magnets_histogram_linear_discrete_Next.txt"
file_path_M =  r"Z:\Projects\Kepler\Halbach\50mT_891ppms_cylindricalCubes\Magnets_histogram_nonlinear_50mT_zigzag_cylindricalCubes.txt"

Br = 1.4  # Tesla 
step_percent = 2

if args.file_path_m:
    file_path_M = args.file_path_m
if args.br is not None:
    Br = args.br
if args.step_percent is not None:
    step_percent = args.step_percent

# Lectura del archivo

data_M = np.loadtxt(file_path_M, comments='%')

M_T = data_M[:, 0]  # mu0_const*mfnc.normM (T)
hist_M = data_M[:, 1]
hist_M_norm = hist_M / np.max(hist_M)
M_percent = (M_T / Br) * 100

# Campo en el máximo

idx_max_M = np.argmax(hist_M)
M_max = M_T[idx_max_M]
hist_M_max = hist_M_norm[idx_max_M]

print(f"M en el máximo = {M_max:.6f} T")
print(f"M/Br en el máximo = {(M_max/Br)*100:.4f} %")

# ==============================
# Plot
# ==============================

fig2, ax2 = plt.subplots(figsize=(8, 5))

# Curva normalizada
ax2.plot(M_T, hist_M_norm, color="grey")
ax2.set_xlabel("Magnetization μ0|M| (T)")
ax2.set_ylabel("Normalized histogram")
ax2.set_title(
    case_title + "\n" + "Magnetization Histogram (Normalized)",
    pad=30,
    fontstyle='italic'
)

# Marcar máximo
color_max = "maroon"

ax2.plot(M_max, hist_M_max, '.', color=color_max)
ax2.annotate(f"{M_max:.4f} T",
             xy=(M_max, hist_M_max),
             xytext=(5, -15),
             textcoords='offset points',
             color=color_max)


# ==========================================
# Eje secundario: M/Br (%)
# ==========================================

def M_to_percent(M_T):
    return (M_T / Br) * 100

def percent_to_M(percent):
    return (percent / 100) * Br

secax2 = ax2.secondary_xaxis('top', functions=(M_to_percent, percent_to_M))
secax2.set_xlabel("Magnetization (% of Br)")

# ============================================================
# Líneas cada X% adaptadas al rango real de los datos
# ============================================================


color = 'royalblue'   # naranjita elegante

# Rango real
p_min_data = np.min(M_percent)
p_max_data = np.max(M_percent)

# Redondeo hacia abajo y hacia arriba al múltiplo de step_percent
p_start = step_percent * np.floor(p_min_data / step_percent)
p_end   = step_percent * np.ceil(p_max_data / step_percent)

percent_edges = np.arange(p_start, p_end + step_percent, step_percent)
secax2.set_xticks(percent_edges)
secax2.set_xticklabels([f"{p:.0f}" for p in percent_edges])

total_volume = np.trapz(hist_M_norm, M_percent)

for i in range(len(percent_edges)-1):
    
    p_min = percent_edges[i]
    p_max = percent_edges[i+1]

    mask = (M_percent >= p_min) & (M_percent < p_max)

    if np.any(mask):
        volume_bin = np.trapz(hist_M_norm[mask], M_percent[mask])
        volume_percent = (volume_bin / total_volume) * 100
    else:
        volume_percent = 0.0

    ax2.axvline(percent_to_M(p_min),
                linestyle='--',
                linewidth=1.2,
                color=color)

    x_text = percent_to_M((p_min + p_max) / 2)
    if volume_percent >= 0.01:
        label_text = f"{volume_percent:.1f}%"
    else:
        label_text = f"{volume_percent:.1e}%"
    ax2.text(x_text,
             1.01,
             label_text,
             ha='center',
             va='bottom',
             fontsize=10,
             rotation=0,
             color=color)

# ============================================================
# Líneas verticales: Mmin real, Mavg, Mmax real
# ============================================================

red_color = 'red'

threshold = 0.00001 * np.max(hist_M)  # 0.1% del máximo
mask_real = hist_M > 0

M_real = M_T[mask_real]
hist_real = hist_M[mask_real]   # <-- usar histograma ORIGINAL

# Valores físicos correctos
M_min = np.min(M_real)
M_max = np.max(M_real)
M_avg = np.average(M_real, weights=hist_real)


print("===================================")
print(f"M_min  = {M_min:.6f} T")
print(f"M_avg  = {M_avg:.6f} T")
print(f"M_max  = {M_max:.6f} T")
print("===================================")

# Función para convertir a %
def to_percent(M):
    return (M / Br) * 100

# Dibujar líneas y etiquetas
labels = [
    f"Min\n{M_min:.3f} T ({to_percent(M_min):.1f}%)",
    f"Avg\n {M_avg:.3f} T ({to_percent(M_avg):.1f}%)",
    f"Max\n {M_max:.3f} T {to_percent(M_max):.1f}%)"
]

for M_value, label in zip([M_min, M_avg, M_max], labels):

    ax2.axvline(M_value,
                color=red_color,
                linestyle=':',
                linewidth=1)

    ax2.text(M_value + 0.0015,   # pequeño desplazamiento horizontal
         0.75,
         label,
         rotation=0,         # sin rotación
         va='center',
         ha='left',
         color=red_color,
         fontsize=9,
         bbox=dict(facecolor='white', alpha=0.8, edgecolor='lightcoral'))

# --- Fecha fuera del plot ---
fecha = datetime.now().strftime("%Y-%m-%d")

fig2.text(0.99, 0.01, fecha,
          ha='right', va='bottom',
          fontsize=10,
          color='gray',
          alpha=0.8)
# Guardar imagen
if args.output_png_m:
    output_path_M = args.output_png_m
elif args.same_name_png:
    output_path_M = os.path.splitext(file_path_M)[0] + ".png"
else:
    output_path_M = file_path_M.replace(".txt", "_magnetization.png")
plt.savefig(output_path_M, dpi=300, bbox_inches='tight')
#plt.xlim(1.34,1.41)
plt.ylim(-0.1,1.09)
#plt.grid()


plt.tight_layout()
plt.show()


