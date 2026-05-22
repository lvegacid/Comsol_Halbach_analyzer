# -*- coding: utf-8 -*-
"""
Created on Wed May 20 16:45:32 2026

@author: cidve
"""

from pathlib import Path

# =========================
# CONFIGURACIÓN
# =========================

# Ruta del archivo .txt
input_path = r"Z:\Projects\PhysioII - NextMRI\Magnet\Comsol\Shimming_arbitrary_rotations\20260520_Odin3_Cube_arbRot2D_3e4Iter_factor1e8_ineq3e-3_81mT_2515ppmsFlat_2529ppmsLinear\campoFOV.txt"

# Índice de la columna a multiplicar
# 0 = primera columna
# 1 = segunda
# 2 = tercera
# 3 = cuarta
column_index = 3

# Factor de multiplicación
factor = 1000

# Etiqueta extra para el nombre de salida
extra_label = "_mT"

# Separador del archivo:
# None -> cualquier espacio/tab
# "," -> csv
separator = None


# =========================
# PROCESADO
# =========================

input_path = Path(input_path)

# Nombre archivo salida
output_path = input_path.with_name(
    input_path.stem + extra_label + input_path.suffix
)

with open(input_path, "r") as f:
    lines = f.readlines()

new_lines = []

for line in lines:

    # Mantener líneas vacías
    if not line.strip():
        new_lines.append(line)
        continue

    # Separar columnas
    if separator is None:
        cols = line.split()
        joiner = "\t"
    else:
        cols = line.strip().split(separator)
        joiner = separator

    # Multiplicar columna elegida
    try:
        value = float(cols[column_index])
        cols[column_index] = f"{value * factor:.12g}"
    except:
        # Si falla (texto/header), deja línea igual
        pass

    new_lines.append(joiner.join(cols) + "\n")

# Guardar
with open(output_path, "w") as f:
    f.writelines(new_lines)

print(f"Archivo guardado en:\n{output_path}")