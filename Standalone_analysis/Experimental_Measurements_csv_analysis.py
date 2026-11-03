from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

CSV_PATH = r"Z:\Projects\Preclinico\Medidas\20260926 1805 Preclinico 10cm9cm_1cm 1000avg 200medidas_20260926_180547.csv"
COMPONENT = "Bx"  # "Bx", "By", "Bz" or "Bnorm"

PLANE_TOLERANCE_CM = 0.5
INCLUDE_PLOTS_2D = True

CMAP = "inferno"
POINT_SIZE_3D = 180
POINT_SIZE_2D = 180
FIGSIZE = (18, 5.2) if INCLUDE_PLOTS_2D else (9, 7)
DPI = 200
SHOW_FIGURE = True

# Si hay muchos puntos, se hace submuestreo solo para visualizacion.
MAX_POINTS_DISPLAY = 30000
RANDOM_SEED = 42


# ============================================================
# HELPERS
# ============================================================

def resolve_component_column(component: str) -> str:
    comp = component.strip().lower()
    if comp == "bx":
        return "Bx_mean (mT)"
    if comp == "by":
        return "By_mean (mT)"
    if comp == "bz":
        return "Bz_mean (mT)"
    if comp == "bnorm":
        return "Bnorm (mT)"
    raise ValueError("COMPONENT must be one of: Bx, By, Bz, Bnorm")


def load_and_validate_csv(csv_path: str) -> pd.DataFrame:
    path = Path(csv_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    if path.stat().st_size == 0:
        raise ValueError(f"CSV file is empty: {path}")

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise ValueError(f"Failed to read CSV: {path}. Details: {exc}") from exc

    if df.empty:
        raise ValueError(f"CSV contains no data rows: {path}")

    required_cols = [
        "X (cm)",
        "Y (cm)",
        "Z (cm)",
        "Bx_mean (mT)",
        "By_mean (mT)",
        "Bz_mean (mT)",
        "N_averages",
        "N_medidas",
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in required_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    numeric_part = df[required_cols]
    if numeric_part.isna().all(axis=None):
        raise ValueError("All numeric columns are empty or non-numeric")

    df = df.dropna(subset=["X (cm)", "Y (cm)", "Z (cm)", "Bx_mean (mT)", "By_mean (mT)", "Bz_mean (mT)"])
    if df.empty:
        raise ValueError("No valid rows remain after cleaning non-numeric values")

    df.attrs["source_path"] = path
    return df


def compute_bnorm(df: pd.DataFrame) -> pd.Series:
    return np.sqrt(
        df["Bx_mean (mT)"] ** 2
        + df["By_mean (mT)"] ** 2
        + df["Bz_mean (mT)"] ** 2
    )


def filter_plane(df: pd.DataFrame, perp_axis: str, tol_cm: float) -> pd.DataFrame:
    return df[np.abs(df[perp_axis]) <= tol_cm].copy()


def sample_for_display(df: pd.DataFrame, max_points: int, seed: int) -> pd.DataFrame:
    if max_points is None or max_points <= 0:
        return df
    if len(df) <= max_points:
        return df
    return df.sample(n=max_points, random_state=seed)


def export_bfov_txt(df: pd.DataFrame, csv_path: Path) -> Path:
    txt_path = csv_path.with_suffix(".txt")
    df_out = pd.DataFrame(
        {
            "x_m": df["X (cm)"] / 100.0,
            "y_m": df["Y (cm)"] / 100.0,
            "z_m": df["Z (cm)"] / 100.0,
            "Bx_mT": df["Bx_mean (mT)"],
            "By_mT": df["By_mean (mT)"],
            "Bz_mT": df["Bz_mean (mT)"],
        }
    )
    df_out.to_csv(txt_path, sep="\t", header=False, index=False, float_format="%.10g")
    return txt_path


def set_3d_axes_equal(ax, x, y, z):
    x_min, x_max = np.nanmin(x), np.nanmax(x)
    y_min, y_max = np.nanmin(y), np.nanmax(y)
    z_min, z_max = np.nanmin(z), np.nanmax(z)

    x_range = x_max - x_min
    y_range = y_max - y_min
    z_range = z_max - z_min

    max_range = max(x_range, y_range, z_range)
    if max_range == 0:
        max_range = 1.0

    x_mid = (x_max + x_min) / 2.0
    y_mid = (y_max + y_min) / 2.0
    z_mid = (z_max + z_min) / 2.0

    half = max_range / 2.0
    ax.set_xlim(x_mid - half, x_mid + half)
    ax.set_ylim(y_mid - half, y_mid + half)
    ax.set_zlim(z_mid - half, z_mid + half)


def plot_plane(ax, df_plane, x_col, y_col, title, xlabel, ylabel, vmin, vmax, component_name):
    if df_plane.empty:
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.text(
            0.5,
            0.5,
            "No points in this plane",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=12,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        return None

    sc = ax.scatter(
        df_plane[x_col],
        df_plane[y_col],
        c=df_plane[component_name],
        cmap=CMAP,
        vmin=vmin,
        vmax=vmax,
        s=POINT_SIZE_2D,
        edgecolors="none",
    )
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(False)
    return sc


# ============================================================
# MAIN
# ============================================================

def main():
    if SHOW_FIGURE:
        try:
            matplotlib.use("TkAgg")
        except Exception:
            matplotlib.use("Agg")
            print("Interactive backend unavailable. Falling back to Agg.", flush=True)
    else:
        matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    csv_path = Path(CSV_PATH).expanduser()
    if not csv_path.is_absolute():
        csv_path = Path.cwd() / csv_path

    df = load_and_validate_csv(str(csv_path))
    bfov_txt_path = export_bfov_txt(df, csv_path)
    print(f"BFOV TXT saved to: {bfov_txt_path}", flush=True)

    component_col = resolve_component_column(COMPONENT)
    if component_col == "Bnorm (mT)":
        df[component_col] = compute_bnorm(df)
    else:
        df[component_col] = pd.to_numeric(df[component_col], errors="coerce")

    df = df.dropna(subset=[component_col])
    if df.empty:
        raise ValueError(f"No valid data for component {COMPONENT}")

    df_plot = sample_for_display(df, MAX_POINTS_DISPLAY, RANDOM_SEED)
    x = df_plot["X (cm)"]
    y = df_plot["Y (cm)"]
    z = df_plot["Z (cm)"]
    b = df_plot[component_col]

    vmin = float(np.nanmin(b))
    vmax = float(np.nanmax(b))
    if vmin == vmax:
        vmax = vmin + 1e-12

    df_xy = filter_plane(df_plot, "Z (cm)", PLANE_TOLERANCE_CM)
    df_yz = filter_plane(df_plot, "X (cm)", PLANE_TOLERANCE_CM)
    df_xz = filter_plane(df_plot, "Y (cm)", PLANE_TOLERANCE_CM)

    print("Generating figure...", flush=True)

    if INCLUDE_PLOTS_2D:
        fig = plt.figure(figsize=FIGSIZE)
        ax3d = fig.add_subplot(141, projection="3d")
        ax_xy = fig.add_subplot(142)
        ax_yz = fig.add_subplot(143)
        ax_xz = fig.add_subplot(144)
    else:
        fig = plt.figure(figsize=FIGSIZE)
        ax3d = fig.add_subplot(111, projection="3d")
        ax_xy = ax_yz = ax_xz = None

    sc3d = ax3d.scatter(
        x,
        y,
        z,
        c=b,
        cmap=CMAP,
        vmin=vmin,
        vmax=vmax,
        s=POINT_SIZE_3D,
        depthshade=False,
        edgecolors="none",
    )
    ax3d.set_title(f"3D - {COMPONENT}")
    ax3d.set_xlabel("X (cm)")
    ax3d.set_ylabel("Y (cm)")
    ax3d.set_zlabel("Z (cm)")
    set_3d_axes_equal(ax3d, x, y, z)

    if INCLUDE_PLOTS_2D:
        plot_plane(
            ax_xy,
            df_xy,
            "X (cm)",
            "Y (cm)",
            f"XY plane | Z≈0 ± {PLANE_TOLERANCE_CM:g} cm",
            "X (cm)",
            "Y (cm)",
            vmin,
            vmax,
            component_col,
        )
        plot_plane(
            ax_yz,
            df_yz,
            "Y (cm)",
            "Z (cm)",
            f"YZ plane | X≈0 ± {PLANE_TOLERANCE_CM:g} cm",
            "Y (cm)",
            "Z (cm)",
            vmin,
            vmax,
            component_col,
        )
        plot_plane(
            ax_xz,
            df_xz,
            "X (cm)",
            "Z (cm)",
            f"XZ plane | Y≈0 ± {PLANE_TOLERANCE_CM:g} cm",
            "X (cm)",
            "Z (cm)",
            vmin,
            vmax,
            component_col,
        )

    fig.suptitle(
        f"Magnetic field visualization - {COMPONENT} | {csv_path.name}",
        fontsize=14,
        y=0.98,
    )

    if INCLUDE_PLOTS_2D:
        cax = fig.add_axes([0.90, 0.16, 0.012, 0.68])
        cbar = fig.colorbar(sc3d, cax=cax)
        fig.subplots_adjust(left=0.04, right=0.87, bottom=0.06, top=0.90, wspace=0.28)
    else:
        cbar = fig.colorbar(sc3d, ax=ax3d, shrink=0.75, pad=0.08)
        fig.tight_layout()

    cbar.set_label("mT")

    output_path = csv_path.with_name(f"{csv_path.stem}_{COMPONENT}.png")
    print("Saving PNG...", flush=True)
    fig.savefig(output_path, dpi=DPI)

    print(f"Rows in CSV: {len(df)} | Plotted points: {len(df_plot)}", flush=True)
    print(f"Figure saved to: {output_path}", flush=True)

    if SHOW_FIGURE and matplotlib.get_backend().lower() != "agg":
        plt.show()
    elif SHOW_FIGURE:
        print("SHOW_FIGURE=True ignored because backend is Agg (non-interactive).", flush=True)

    plt.close(fig)


if __name__ == "__main__":
    main()

