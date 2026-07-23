from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

from app.models.entities import AttachedImageInfo, MagnetMetrics, RingInfo


class MagnetDataService:
    EXPECTED_COLUMNS = ["x", "y", "z", "Br", "mx", "my", "mz", "sx", "sy", "sz"]
    M_TO_MM = 1000.0
    CENTER_ZERO_TOL_MM = 1e-3

    @staticmethod
    def _fmt_measure(value: float, decimals: int = 3) -> str:
        return (f"{float(value):.{decimals}f}").rstrip("0").rstrip(".")

    @staticmethod
    def detect_expected_ppm_from_filename(txt_path: str) -> float | None:
        name = Path(txt_path).name
        match = re.search(r"(\d+(?:\.\d+)?)ppm", name, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def parse_txt(
        self,
        txt_path: str,
        project: str,
        magnet_characteristics: str,
        comsol_version: str,
        run_date: str,
        expected_ppm: float | None = None,
        other_information: str = "",
        other_info_images: list[AttachedImageInfo] | None = None,
    ) -> MagnetMetrics:
        path = Path(txt_path)
        if not path.exists():
            raise FileNotFoundError(f"TXT file not found: {txt_path}")

        df = pd.read_csv(path, sep=r"\s+", header=None, engine="python")
        if df.shape[1] < len(self.EXPECTED_COLUMNS):
            raise ValueError(
                f"Expected at least {len(self.EXPECTED_COLUMNS)} columns, got {df.shape[1]}"
            )

        df = df.iloc[:, : len(self.EXPECTED_COLUMNS)].copy()
        df.columns = self.EXPECTED_COLUMNS

        n_magnets = int(len(df))

        # Convert geometric data from meters to millimeters for reporting.
        for col in ("x", "y", "z", "sx", "sy", "sz"):
            df[col] = df[col].astype(float) * self.M_TO_MM

        grouped = df.groupby("x", sort=True).size().reset_index(name="magnets")
        rings = [
            RingInfo(ring_index=i + 1, x_position_mm=float(row["x"]), magnets=int(row["magnets"]))
            for i, (_, row) in enumerate(grouped.iterrows())
        ]

        n_rings = len(rings)

        br_t = float(df["Br"].mean())

        sx = float(df["sx"].median())
        sy = float(df["sy"].median())
        sz = float(df["sz"].median())
        magnet_size_mm3 = (
            f"{self._fmt_measure(sx)} x {self._fmt_measure(sy)} x {self._fmt_measure(sz)}"
        )

        magnet_length_mm = float(df["x"].max() - df["x"].min())

        y_centers = df["y"].to_numpy(dtype=float)
        z_centers = df["z"].to_numpy(dtype=float)

        y_length_min, y_length_max = self._compute_axis_length_range_mm(axis_centers=y_centers, orthogonal_centers=z_centers)
        z_length_min, z_length_max = self._compute_axis_length_range_mm(axis_centers=z_centers, orthogonal_centers=y_centers)

        size_triplets = np.round(df[["sx", "sy", "sz"]].to_numpy(dtype=float), 6)
        unique_triplets = np.unique(size_triplets, axis=0)
        interring_distance_mm: float | None = None
        interring_note = ""
        if len(unique_triplets) == 1:
            unique_x = np.sort(np.unique(df["x"].to_numpy(dtype=float)))
            if unique_x.size >= 2:
                first_x = float(unique_x[0])
                second_x = float(unique_x[1])
                center_to_center = abs(second_x - first_x)
                magnet_size_x = float(unique_triplets[0][0])
                interring_distance_mm = center_to_center - magnet_size_x
            else:
                interring_note = "InterRing distance not computed."
        else:
            interring_note = "Different magnet sizes detected. InterRing distance not computed."

        return MagnetMetrics(
            project=project,
            magnet_characteristics=magnet_characteristics or path.name,
            comsol_version=comsol_version,
            run_date=run_date,
            txt_path=str(path),
            n_magnets=n_magnets,
            n_rings=n_rings,
            br_t=br_t,
            magnet_size_mm3=magnet_size_mm3,
            magnet_length_mm=magnet_length_mm,
            y_length_min_mm=y_length_min,
            y_length_max_mm=y_length_max,
            z_length_min_mm=z_length_min,
            z_length_max_mm=z_length_max,
            interring_distance_mm=interring_distance_mm,
            interring_note=interring_note,
            expected_ppm=expected_ppm,
            other_information=other_information,
            other_info_images=[AttachedImageInfo(path=item.path, comment=item.comment) for item in (other_info_images or [])],
            rings=rings,
        )

    def _compute_axis_length_range_mm(self, axis_centers: np.ndarray, orthogonal_centers: np.ndarray) -> tuple[float, float]:
        # Primary path: keep only centers lying on the orthogonal near-zero plane.
        near_zero = np.isclose(orthogonal_centers, 0.0, atol=self.CENTER_ZERO_TOL_MM)
        selected = axis_centers[near_zero]

        if selected.size == 0:
            # Fallback: if no exact near-zero centers exist, use the closest orthogonal slice.
            min_abs = float(np.min(np.abs(orthogonal_centers))) if orthogonal_centers.size else 0.0
            closest = np.isclose(np.abs(orthogonal_centers), min_abs, atol=self.CENTER_ZERO_TOL_MM)
            selected = axis_centers[closest]

        if selected.size == 0:
            return 0.0, 0.0

        abs_selected = np.abs(selected.astype(float))
        axis_min_abs = float(np.min(abs_selected))
        axis_max_abs = float(np.max(abs_selected))
        return axis_min_abs * 2.0, axis_max_abs * 2.0
