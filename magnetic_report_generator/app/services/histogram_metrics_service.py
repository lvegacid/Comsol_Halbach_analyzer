from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from app.models.entities import SimulationStudyResult


class HistogramMetricsService:
    HEADER_TO_KEY = {
        "P2P ppm": "P2P ppm",
        "P2P kHz": "P2P kHz",
        "P2P (kHz)": "P2P kHz",
        "B_min": "B_min",
        "B_min (mT)": "B_min",
        "B_min kHz": "B_min kHz",
        "B_min (kHz)": "B_min kHz",
        "B_max": "B_max",
        "B_max (mT)": "B_max",
        "B_max kHz": "B_max kHz",
        "B_max (kHz)": "B_max kHz",
        "B_avg": "B_avg",
        "B_avg (mT)": "B_avg",
        "B_avg kHz": "B_avg kHz",
        "B_avg (kHz)": "B_avg kHz",
        "1-99% ppm": "1-99% ppm",
        "1-99% kHz": "1-99% kHz",
        "1-99% (kHz)": "1-99% kHz",
        "P1": "P1",
        "P1 (mT)": "P1",
        "P1 kHz": "P1 kHz",
        "P1 (kHz)": "P1 kHz",
        "P99": "P99",
        "P99 (mT)": "P99",
        "P99 kHz": "P99 kHz",
        "P99 (kHz)": "P99 kHz",
        "5-95% ppm": "5-95% ppm",
        "5-95% kHz": "5-95% kHz",
        "5-95% (kHz)": "5-95% kHz",
        "P5": "P5",
        "P5 (mT)": "P5",
        "P5 kHz": "P5 kHz",
        "P5 (kHz)": "P5 kHz",
        "P95": "P95",
        "P95 (mT)": "P95",
        "P95 kHz": "P95 kHz",
        "P95 (kHz)": "P95 kHz",
        "Peak": "Peak",
        "Peak (mT)": "Peak",
        "Peak kHz": "Peak kHz",
        "Peak (kHz)": "Peak kHz",
    }
    COLUMNS = [
        "Label",
        "P2P ppm",
        "P2P kHz",
        "B_min (mT)",
        "B_min (kHz)",
        "B_max (mT)",
        "B_max (kHz)",
        "B_avg (mT)",
        "B_avg (kHz)",
        "1-99% ppm",
        "1-99% kHz",
        "P1 (mT)",
        "P1 (kHz)",
        "P99 (mT)",
        "P99 (kHz)",
        "5-95% ppm",
        "5-95% kHz",
        "P5 (mT)",
        "P5 (kHz)",
        "P95 (mT)",
        "P95 (kHz)",
        "Peak (mT)",
        "Peak (kHz)",
    ]

    def __init__(self) -> None:
        self._script_path = Path(__file__).resolve().parents[4] / "Comsol_extracted_histograms_BFOV_Magnets.py"

    def ensure_metrics_for_study(self, study: SimulationStudyResult) -> dict[str, dict[str, float]]:
        output_file = Path(study.folder_path) / f"{study.folder_name}_Data_extracted_histograms.txt"
        existing = self._read_existing_metrics(output_file)
        candidates = self._collect_histogram_candidates(study, output_file)
        added_any = False

        for label in sorted(candidates.keys()):
            if label in existing:
                continue

            metrics = self._compute_metrics_from_histogram(candidates[label])
            if metrics is None:
                continue
            existing[label] = metrics
            added_any = True

        if added_any or not output_file.exists():
            self._write_metrics_file(output_file, existing)
        return existing

    def _collect_histogram_candidates(self, study: SimulationStudyResult, output_file: Path) -> dict[str, Path]:
        candidates: dict[str, Path] = {}

        # Prefer parsed study-domain mapping first.
        for domain in study.domains:
            txt_path = None
            if domain.histogram_txt:
                candidate = Path(domain.histogram_txt)
                if candidate.exists():
                    txt_path = candidate
            elif domain.histogram:
                candidate = Path(domain.histogram).with_suffix(".txt")
                if candidate.exists():
                    txt_path = candidate

            if txt_path is not None:
                candidates[domain.name] = txt_path

        # Include magnets histogram when present.
        if study.magnets.histogram:
            magnets_txt = Path(study.magnets.histogram).with_suffix(".txt")
            if magnets_txt.exists() and "Magnets" not in candidates:
                candidates["Magnets"] = magnets_txt

        # Discover histogram TXT files from histogram PNG naming patterns.
        for png_path in Path(study.folder_path).rglob("*.png"):
            label = self._label_from_histogram_png_stem(png_path.stem)
            if not label:
                continue
            guessed_txt = self._guess_histogram_txt_from_png(png_path)
            if guessed_txt is not None:
                candidates.setdefault(label, guessed_txt)

        # Fallback discovery across the full study tree.
        for txt_path in Path(study.folder_path).rglob("*.txt"):
            if txt_path.resolve() == output_file.resolve():
                continue
            label = self._label_from_histogram_txt(study.folder_name, txt_path)
            if not label:
                continue
            candidates.setdefault(label, txt_path)

        return candidates

    def _label_from_histogram_png_stem(self, stem: str) -> str | None:
        lower_name = stem.lower()
        if "histogram" not in lower_name:
            return None

        if lower_name.startswith("bfov_histogram"):
            return "FOV"
        if lower_name.startswith("magnets_histogram"):
            return "Magnets"

        marker = "_histogram_"
        if lower_name.startswith("b_") and marker in lower_name:
            idx = lower_name.find(marker)
            if idx > 2:
                domain = stem[2:idx].strip(" _")
                if domain:
                    return domain

        match = re.match(r"^B_(?P<domain>.+?)_Histogram", stem, flags=re.IGNORECASE)
        if match:
            domain = match.group("domain").strip(" _")
            if domain:
                return domain

        return None

    def _guess_histogram_txt_from_png(self, png_path: Path) -> Path | None:
        same_name = png_path.with_suffix(".txt")
        if same_name.exists():
            return same_name

        stem = png_path.stem
        alternatives: list[str] = []
        if stem.startswith("BFOV_histogram_"):
            alternatives.append(stem.replace("BFOV_histogram_", "BFOV_", 1))
        if stem.startswith("Magnets_histogram_"):
            alternatives.append(stem.replace("Magnets_histogram_", "Magnets_", 1))
        if "_Histogram_" in stem and stem.startswith("B_"):
            alternatives.append(stem.replace("_Histogram_", "_", 1))

        for alt_stem in alternatives:
            candidate = png_path.with_name(f"{alt_stem}.txt")
            if candidate.exists():
                return candidate

        return None

    def _label_from_histogram_txt(self, study_folder_name: str, txt_path: Path) -> str | None:
        stem = txt_path.stem
        lower_name = stem.lower()
        if lower_name == f"{study_folder_name.lower()}_data_extracted_histograms":
            return None

        if lower_name.startswith("bfov_histogram"):
            return "FOV"
        if lower_name.startswith("bfov_"):
            return "FOV"
        if lower_name.startswith("magnets_histogram"):
            return "Magnets"
        if lower_name.startswith("magnets_"):
            return "Magnets"

        if "histogram" not in lower_name:
            return None

        marker = "_histogram_"
        if lower_name.startswith("b_") and marker in lower_name:
            idx = lower_name.find(marker)
            if idx > 2:
                domain = stem[2:idx].strip(" _")
                if domain:
                    return domain

        match = re.match(r"^B_(?P<domain>.+?)_Histogram", stem, flags=re.IGNORECASE)
        if match:
            domain = match.group("domain").strip(" _")
            if domain:
                return domain

        return None

    def _compute_metrics_from_histogram(self, histogram_txt: Path) -> dict[str, float] | None:
        if not histogram_txt.exists():
            return None

        local_metrics = self._compute_metrics_locally(histogram_txt)
        if local_metrics is not None:
            return local_metrics

        if not self._script_path.exists():
            return None

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8") as tmp:
            metrics_json = Path(tmp.name)

        cmd = [
            sys.executable,
            str(self._script_path),
            "--file-path",
            str(histogram_txt),
            "--bfov-only",
            "--no-show",
            "--emit-metrics-json",
            str(metrics_json),
        ]

        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if completed.returncode != 0 or not metrics_json.exists():
                return None
            with metrics_json.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            return {
                "P2P ppm": float(raw["P2P_ppm"]),
                "B_min": float(raw["B_min"]),
                "B_max": float(raw["B_max"]),
                "B_avg": float(raw["B_avg"]),
                "1-99% ppm": float(raw["ppm_1_99"]),
                "P1": float(raw["P1"]),
                "P99": float(raw["P99"]),
                "5-95% ppm": float(raw["ppm_5_95"]),
                "P5": float(raw["P5"]),
                "P95": float(raw["P95"]),
                "Peak": float(raw["Peak"]),
                "BW_p2p_Hz": float(raw["BW_p2p_Hz"]),
                "BW_1_99_Hz": float(raw["BW_1_99_Hz"]),
                "BW_5_95_Hz": float(raw["BW_5_95_Hz"]),
            }
        finally:
            try:
                metrics_json.unlink(missing_ok=True)
            except Exception:
                pass

    def _compute_metrics_locally(self, histogram_txt: Path) -> dict[str, float] | None:
        try:
            data = np.loadtxt(str(histogram_txt), comments="%")
            if data.ndim == 1:
                if data.size < 2:
                    return None
                data = np.array([data])
            if data.shape[1] < 2:
                return None

            b_mt = data[:, 0].astype(float)
            hist = data[:, 1].astype(float)
            if b_mt.size == 0 or hist.size == 0:
                return None

            mask = hist > 0
            if not np.any(mask):
                return None

            b_real = b_mt[mask]
            hist_real = hist[mask]

            b_min = float(np.min(b_real))
            b_max = float(np.max(b_real))
            b_avg = float(np.average(b_real, weights=hist_real))
            if abs(b_avg) < 1e-12:
                return None

            idx_peak = int(np.argmax(hist))
            b_peak = float(b_mt[idx_peak])

            p1 = self._weighted_percentile(b_mt, hist, 1.0)
            p5 = self._weighted_percentile(b_mt, hist, 5.0)
            p95 = self._weighted_percentile(b_mt, hist, 95.0)
            p99 = self._weighted_percentile(b_mt, hist, 99.0)

            ppm_p2p = (b_max - b_min) / b_avg * 1e6
            ppm_1_99 = (p99 - p1) / b_avg * 1e6
            ppm_5_95 = (p95 - p5) / b_avg * 1e6

            gamma = 42.58e6

            def b_to_khz(b_val: float) -> float:
                return ((b_val - b_peak) * 1e-3 * gamma) / 1e3

            bw_p2p_hz = (b_to_khz(b_max) - b_to_khz(b_min)) * 1e3
            bw_1_99_hz = (b_to_khz(p99) - b_to_khz(p1)) * 1e3
            bw_5_95_hz = (b_to_khz(p95) - b_to_khz(p5)) * 1e3

            return {
                "P2P ppm": float(ppm_p2p),
                "B_min": float(b_min),
                "B_max": float(b_max),
                "B_avg": float(b_avg),
                "1-99% ppm": float(ppm_1_99),
                "P1": float(p1),
                "P99": float(p99),
                "5-95% ppm": float(ppm_5_95),
                "P5": float(p5),
                "P95": float(p95),
                "Peak": float(b_peak),
                "BW_p2p_Hz": float(bw_p2p_hz),
                "BW_1_99_Hz": float(bw_1_99_hz),
                "BW_5_95_Hz": float(bw_5_95_hz),
            }
        except Exception:
            return None

    @staticmethod
    def _weighted_percentile(values: np.ndarray, weights: np.ndarray, percentile: float) -> float:
        order = np.argsort(values)
        v_sorted = values[order]
        w_sorted = weights[order]
        cdf = np.cumsum(w_sorted)
        total = cdf[-1] if cdf.size else 0.0
        if total <= 0:
            return float(v_sorted[0])
        return float(np.interp(percentile / 100.0, cdf / total, v_sorted))

    def _read_existing_metrics(self, output_file: Path) -> dict[str, dict[str, float]]:
        if not output_file.exists():
            return {}

        lines = output_file.read_text(encoding="utf-8").splitlines()
        if len(lines) < 2:
            return {}

        headers = [part.strip() for part in lines[0].split("\t")]
        if not headers or headers[0] != "Label":
            return {}

        out: dict[str, dict[str, float]] = {}
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            label = parts[0].strip()
            if not label:
                continue
            values: dict[str, float] = {}
            for i, col in enumerate(headers[1:], start=1):
                if i >= len(parts):
                    continue
                key = self.HEADER_TO_KEY.get(col, col)
                try:
                    values[key] = float(parts[i])
                except ValueError:
                    values[key] = 0.0
            out[label] = values
        return out

    def _write_metrics_file(self, output_file: Path, metrics_by_label: dict[str, dict[str, float]]) -> None:
        rows = ["\t".join(self.COLUMNS)]
        for label in sorted(metrics_by_label.keys()):
            m = metrics_by_label[label]
            row = [
                label,
                self._fmt(m.get("P2P ppm", 0.0)),
                self._fmt(m.get("P2P kHz", self._khz_value(m, "P2P ppm"))),
                self._fmt(m.get("B_min", 0.0)),
                self._fmt(m.get("B_min kHz", self._khz_value(m, "Bmin"))),
                self._fmt(m.get("B_max", 0.0)),
                self._fmt(m.get("B_max kHz", self._khz_value(m, "Bmax"))),
                self._fmt(m.get("B_avg", 0.0)),
                self._fmt(m.get("B_avg kHz", self._khz_value(m, "Bavg"))),
                self._fmt(m.get("1-99% ppm", 0.0)),
                self._fmt(m.get("1-99% kHz", self._khz_value(m, "1-99% ppm"))),
                self._fmt(m.get("P1", 0.0)),
                self._fmt(m.get("P1 kHz", self._khz_value(m, "P1"))),
                self._fmt(m.get("P99", 0.0)),
                self._fmt(m.get("P99 kHz", self._khz_value(m, "P99"))),
                self._fmt(m.get("5-95% ppm", 0.0)),
                self._fmt(m.get("5-95% kHz", self._khz_value(m, "5-95% ppm"))),
                self._fmt(m.get("P5", 0.0)),
                self._fmt(m.get("P5 kHz", self._khz_value(m, "P5"))),
                self._fmt(m.get("P95", 0.0)),
                self._fmt(m.get("P95 kHz", self._khz_value(m, "P95"))),
                self._fmt(m.get("Peak", 0.0)),
                self._fmt(m.get("Peak kHz", self._khz_value(m, "Peak"))),
            ]
            rows.append("\t".join(row))

        output_file.write_text("\n".join(rows) + "\n", encoding="utf-8")

    @staticmethod
    def _khz_value(metrics: dict[str, float], parameter: str) -> float:
        gamma_khz_per_mt = 42.58
        peak = float(metrics.get("Peak", 0.0))
        if parameter == "P2P ppm":
            bw = float(metrics.get("BW_p2p_Hz", 0.0))
            if bw == 0.0:
                bw = (float(metrics.get("B_max", 0.0)) - float(metrics.get("B_min", 0.0))) * gamma_khz_per_mt * 1000.0
            return bw / 1000.0
        if parameter == "Bmin":
            return (float(metrics.get("B_min", 0.0)) - peak) * gamma_khz_per_mt
        if parameter == "Bmax":
            return (float(metrics.get("B_max", 0.0)) - peak) * gamma_khz_per_mt
        if parameter == "Bavg":
            return (float(metrics.get("B_avg", 0.0)) - peak) * gamma_khz_per_mt
        if parameter == "1-99% ppm":
            bw = float(metrics.get("BW_1_99_Hz", 0.0))
            if bw == 0.0:
                bw = (float(metrics.get("P99", 0.0)) - float(metrics.get("P1", 0.0))) * gamma_khz_per_mt * 1000.0
            return bw / 1000.0
        if parameter == "P1":
            return (float(metrics.get("P1", 0.0)) - peak) * gamma_khz_per_mt
        if parameter == "P99":
            return (float(metrics.get("P99", 0.0)) - peak) * gamma_khz_per_mt
        if parameter == "5-95% ppm":
            bw = float(metrics.get("BW_5_95_Hz", 0.0))
            if bw == 0.0:
                bw = (float(metrics.get("P95", 0.0)) - float(metrics.get("P5", 0.0))) * gamma_khz_per_mt * 1000.0
            return bw / 1000.0
        if parameter == "P5":
            return (float(metrics.get("P5", 0.0)) - peak) * gamma_khz_per_mt
        if parameter == "P95":
            return (float(metrics.get("P95", 0.0)) - peak) * gamma_khz_per_mt
        return 0.0

    @staticmethod
    def _fmt(value: float) -> str:
        return f"{float(value):.3f}"
