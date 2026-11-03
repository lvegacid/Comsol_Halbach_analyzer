import numpy as np
import matplotlib.pyplot as plt
import os

#%% ===============================
# 1. Generar archivo .txt con coordenadas de esfera: De polares a cartesianas
# ===============================

# Parámetros del problema
n_theta = 400
n_phi   = 400
R       = 0.34/2   # radio de la esfera [m]


# Rutas y nombre de archivo (automático)
output_dir = r"Z:\Projects\Kepler\Halbach\90mT\BFOV_Comsol_extracted"

output_name = (
    f"Coordenadas_esfera_"
    f"R_{R:.3f}_"
    f"ntheta_{n_theta}_"
    f"nphi_{n_phi}.txt"
)

output_path = os.path.join(output_dir, output_name)
os.makedirs(output_dir, exist_ok=True)


# Generar coordenadas de la esfera (polares → cartesianas)
theta = np.linspace(0, 2*np.pi, n_theta)
phi   = np.linspace(0, np.pi, n_phi)

theta_grid, phi_grid = np.meshgrid(theta, phi)

x = R * np.sin(phi_grid) * np.cos(theta_grid)
y = R * np.sin(phi_grid) * np.sin(theta_grid)
z = R * np.cos(phi_grid)

coords = np.column_stack((x.ravel(), y.ravel(), z.ravel()))

np.savetxt(output_path, coords, fmt="%.6e")

print(f"Archivo generado correctamente en:\n{output_path}")

#
# Visualización
fig = plt.figure(figsize=(6, 6))
ax = fig.add_subplot(111, projection="3d")

ax.scatter(x, y, z, s=10, c=z, cmap="viridis")
ax.set_xlabel("X [m]")
ax.set_ylabel("Y [m]")
ax.set_zlabel("Z [m]")
ax.set_title(f"Esfera R = {R:.3f} m")

plt.tight_layout()
plt.show()

# 4. Distancia angular entre puntos (criterio de resolución)
# ===============================

# Pasos angulares
dtheta = 2 * np.pi / (n_theta - 1)
dphi   = np.pi / (n_phi - 1)

# Distancia angular máxima entre puntos vecinos (en radianes)
dalpha_max = max(dtheta, dphi)

# Distancia lineal sobre la esfera (arco máximo)
ds_max = R * dalpha_max

print("==== Resolución angular de la esfera ====")
print(f"dtheta = {dtheta:.3e} rad")
print(f"dphi   = {dphi:.3e} rad")
print(f"dalpha_max = {dalpha_max:.3e} rad")
print(f"Distancia máxima entre puntos vecinos ≈ {ds_max*1000} mm")


#%% ===============================
# 3. Leer archivo .txt generado en COMSOL para B_FOV con las coordenadas y las columnas de resultados
# ===============================
# Archivo exportado desde COMSOL (asegúrate que el nombre coincide)
#filename = r"Z:\Projects\Kepler\Halbach\90mT\BFOV_Comsol_extracted\COMSOL_BFOV_R_0.100_ntheta_100_nphi_100.txt"

# Carpeta donde COMSOL exporta los BFOV
input_dir = r"Z:\Projects\Kepler\Halbach\90mT\BFOV_Comsol_extracted"

# Tag COMSOL (misma convención siempre)
tag = f"R_{R:.3f}_ntheta_{n_theta}_nphi_{n_phi}"

# Nombre del archivo COMSOL
filename = os.path.join(
    input_dir,
    f"COMSOL_BFOV_{tag}.txt"
)

print(f"Archivo COMSOL a leer:\n{filename}")

# Cargar ignorando las líneas de cabecera que empiezan con "%"
data = np.loadtxt(filename, comments="%")

# Separar columnas
x_c, y_c, z_c, B_c = data[:,0], data[:,1], data[:,2], data[:,4]

# Calcular ppms
B_mean = np.mean(B_c)
B_max  = np.max(B_c)
B_min  = np.min(B_c)

inhomogeneity = (B_max - B_min)*1E6 / B_mean

print("==== Métricas del campo magnético (COMSOL) ====")
print(f"B_mean = {B_mean:.3f} mT")
print(f"B_max  = {B_max:.3f} mT")
print(f"B_min  = {B_min:.3f} mT")
print(f"{inhomogeneity:.2f} ppm")

#Plot incluyendo ppms en título
fig = plt.figure(figsize=(7, 6))
ax = fig.add_subplot(111, projection="3d")

p = ax.scatter(
    x_c, y_c, z_c,
    c=B_c,
    s=300,
    cmap="plasma"
)

ax.set_xlabel("X [m]")
ax.set_ylabel("Y [m]")
ax.set_zlabel("Z [m]")

ax.set_title(
    "Campo magnético importado de COMSOL\n"
    f"Inhomogeneidad = {inhomogeneity:.2f} ppm\n"
    f"Bmax = {B_max:.2f} mT   "
    f"Bmin = {B_min:.2f} mT   "
    f"<B> = {B_mean:.2f} mT"
)

cbar = fig.colorbar(p, ax=ax)
cbar.set_label("B_y [mT]")

# Guardar figura en la misma carpeta que el archivo COMSOL
output_fig = os.path.join(
    input_dir,
    f"COMSOL_BFOV_{tag}.png"
)
print(f"Figura se guardará en:\n{output_fig}")
plt.savefig(output_fig, dpi=150, bbox_inches="tight")
plt.show()

print(f"Figura guardada en:\n{output_fig}")




#%% ===============================
# Metricas
# ===============================

# -------------------------------
# Métrica 1: Peak-to-peak (ppm)
# -------------------------------
Bmax = np.max(B_c)
Bmin = np.min(B_c)
Bavg = np.mean(B_c)

ppm_peak_to_peak = (Bmax - Bmin) * 1e6 / Bavg

print("\n==== METRICA: Peak-to-peak (volume sampled) ====")
print(f"Bmax = {Bmax:.6f} mT")
print(f"Bmin = {Bmin:.6f} mT")
print(f"Bavg = {Bavg:.6f} mT")
print(f"Peak-to-peak homogeneity = {ppm_peak_to_peak:.2f} ppm")


# -------------------------------
# Métrica 2: Desviación estándar (ppm)
# -------------------------------
B_std = np.std(B_c)

ppm_std = B_std * 1e6 / Bavg

print("\n==== METRICA: Standard deviation (volume sampled) ====")
print(f"Std(B) = {B_std:.6e} mT")
print(f"Std homogeneity = {ppm_std:.2f} ppm")


# -------------------------------
# Métrica 3: Percentiles (P95–P5)
# -------------------------------
P95 = np.percentile(B_c, 95)
P05 = np.percentile(B_c, 5)

ppm_percentile = (P95 - P05) * 1e6 / Bavg

print("\n==== METRICA: Percentile-based (P95–P5) ====")
print(f"P95 = {P95:.6f} mT")
print(f"P05 = {P05:.6f} mT")
print(f"Percentile homogeneity (P95–P5) = {ppm_percentile:.2f} ppm")


# -------------------------------
# Métrica 4: Percentiles (P99–P1)
# -------------------------------
P99 = np.percentile(B_c, 99)
P01 = np.percentile(B_c, 1)

ppm_percentile_99_1 = (P99 - P01) * 1e6 / Bavg

print("\n==== METRICA: Percentile-based (P99–P1) ====")
print(f"P99 = {P99:.6f} mT")
print(f"P01 = {P01:.6f} mT")
print(f"Percentile homogeneity (P99–P1) = {ppm_percentile_99_1:.2f} ppm")


#%% ===============================
# Plot B vs IDnumber (sampled points) con color por Z
# ===============================

# ID de cada punto (orden de muestreo)
ID = np.arange(len(B_c))

# Normalización de colores usando Z (misma idea que la esferita)
norm = plt.Normalize(vmin=z_c.min(), vmax=z_c.max())
cmap = plt.cm.viridis
colors = cmap(norm(z_c))

fig, ax = plt.subplots(figsize=(8, 4))

sc = ax.scatter(
    ID,
    B_c,
    c=z_c,
    cmap=cmap,
    s=2
)

ax.set_xlabel("ID number (sample index)")
ax.set_ylabel("B_y [mT]")

ax.set_title(
    "Magnetic field sampled over FOV surface\n"
    f"B vs ID number (colored by Z)  (N = {len(B_c)})"
)

ax.grid(True, alpha=0.3)

# Colorbar consistente con la esferita
cbar = plt.colorbar(sc, ax=ax)
cbar.set_label("Z [m]")

output_fig_id = os.path.join(
    input_dir,
    f"COMSOL_BFOV_{tag}_B_vs_ID_colored_by_Z.png"
)

plt.tight_layout()
plt.savefig(output_fig_id, dpi=150, bbox_inches="tight")
plt.show()

print("Figura B vs ID (coloreada por Z) guardada en:")
print(output_fig_id)


#%% ===============================
# Plot B vs IDnumber (sampled points) con color por radio XY
# ===============================

# ID de cada punto (orden de muestreo)
ID = np.arange(len(B_c))

# Radio transversal (distancia al eje Z)
rho_xy = np.sqrt(x_c**2 + y_c**2)

# Normalización de colores
norm = plt.Normalize(vmin=rho_xy.min(), vmax=rho_xy.max())
cmap = plt.cm.viridis

fig, ax = plt.subplots(figsize=(8, 4))

sc = ax.scatter(
    ID,
    B_c,
    c=rho_xy,
    cmap=cmap,
    s=1
)

ax.set_xlabel("ID number (sample index)")
ax.set_ylabel("B_y [mT]")

ax.set_title(
    "Magnetic field sampled over FOV surface\n"
    f"B vs ID number (colored by radial distance in XY)"
)

ax.grid(True, alpha=0.3)

# Colorbar: distancia al eje
cbar = plt.colorbar(sc, ax=ax)
cbar.set_label(r"$\rho_{XY} = \sqrt{x^2 + y^2}$  [m]")

output_fig_id = os.path.join(
    input_dir,
    f"COMSOL_BFOV_{tag}_B_vs_ID_colored_by_rXY.png"
)

plt.tight_layout()
plt.savefig(output_fig_id, dpi=150, bbox_inches="tight")
plt.show()

print("Figura B vs ID (coloreada por radio XY) guardada en:")
print(output_fig_id)




#%% ===============================
# 2. Generar archivo .txt con coordenadas de centros de los cubos 
# ===============================


# Carpeta donde están los archivos
folder = r"Z:\Projects\Kepler\Halbach\90mT"

# Nombre del archivo de entrada (dentro de la carpeta)
filename = "fullbody_90mT_55ppms(cube).txt"

# === Construcción de paths ===
input_file = os.path.join(folder, filename)
output_file = os.path.join(folder, f"{filename}_Coordinates_center_cubes")

# === Lectura y filtrado ===
data = np.loadtxt(input_file)
coords = data[:, :3]  # Solo columnas x, y, z

# === Escritura ===
np.savetxt(output_file, coords, fmt="%.6f", delimiter="\t")

print(f"Archivo generado: {output_file}")

#%% ===============================
# Plot automático de resultados COMSOL
# ===============================

# Archivo exportado desde COMSOL
filename = r"Z:\# MRI group\Lorena\Comsol simulations\Hallbach rings\Modelos_Fer\Coordinate_evaluation\20250902_B_FOV_50mT_Br-1_4T__mu_r-1_05.txt"

# === Leer cabeceras manualmente (para sacar nombres de columnas) ===
with open(filename, "r") as f:
    header_lines = []
    for line in f:
        if line.startswith("%") or line.strip() == "":
            header_lines.append(line)
        else:
            break

# Última línea de cabecera contiene nombres de columnas
column_names = header_lines[-1].strip().split()
# Ejemplo: ['x', 'y', 'z', 'mfnc.Bx', 'mfnc.By', 'mfnc.Bz', 'mfnc.normB']

# === Cargar datos numéricos ===
data = np.loadtxt(filename, comments="%")

# Separar coordenadas
x, y, z = data[:, 0], data[:, 1], data[:, 2]

# Carpeta de salida para plots
out_dir = os.path.dirname(filename)
# Empieza desde la columna 3 (cuarta columna) hasta la última disponible
for i in range(3, data.shape[1]):  
    col_name = column_names[i] if i < len(column_names) else f"Column_{i+1}"
    values = data[:, i]

    fig = plt.figure(figsize=(7, 6))
    ax = fig.add_subplot(111, projection="3d")
    p = ax.scatter(x, y, z, c=values, s=8, cmap="plasma")

    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")

    clean_name = col_name.replace("mfnc.", "")
    ax.set_title(f"Campo magnético: B{clean_name}")
    fig.colorbar(p, ax=ax, label=clean_name)

    out_file = os.path.join(out_dir, f"Comsol_{clean_name}.png")
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.show()

    print(f"Plot guardado: {out_file}")