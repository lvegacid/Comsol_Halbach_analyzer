from __future__ import annotations

from html import escape
import os
from pathlib import Path
import tempfile
import uuid

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.entities import AttachedImageInfo, MagnetMetrics, MaterialCurve, ReportPayload, SimulationStudyResult


class ReportService:
    def __init__(self) -> None:
        self._temp_image_paths: list[Path] = []
        styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#17324D"),
        )
        self.h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=colors.HexColor("#1F3C5A"))
        self.h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#2A567B"))
        self.h3 = ParagraphStyle("H3", parent=styles["Heading3"], textColor=colors.HexColor("#356E96"))
        self.normal = styles["BodyText"]
        self.cell = ParagraphStyle("Cell", parent=styles["BodyText"], wordWrap="CJK", fontSize=9)
        self.study_title = ParagraphStyle(
            "StudyTitle",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#1D5F9A"),
            spaceBefore=2,
            spaceAfter=4,
        )

    def generate(self, payload: ReportPayload) -> None:
        fmt = (payload.output_format or "pdf").strip().lower()
        if fmt == "md":
            self.generate_markdown(payload)
            return
        self.generate_pdf(payload)

    def generate_pdf(self, payload: ReportPayload) -> None:
        self._temp_image_paths = []
        doc = SimpleDocTemplate(
            str(payload.output_path),
            pagesize=A4,
            leftMargin=1.8 * cm,
            rightMargin=1.8 * cm,
            topMargin=1.6 * cm,
            bottomMargin=1.8 * cm,
            title="Magnetic Simulation Report",
        )

        story = []
        title = "Magnetic Simulation Report Generator"
        subtitle = ""
        if payload.magnet_metrics is not None:
            title = payload.magnet_metrics.project or title
            subtitle = payload.magnet_metrics.magnet_characteristics or Path(payload.magnet_metrics.txt_path).name

        story.append(Paragraph(escape(title), self.title_style))
        story.append(Spacer(1, 0.4 * cm))
        if subtitle:
            story.append(Paragraph(escape(subtitle), self.h3))
            story.append(Spacer(1, 0.15 * cm))
        self._append_index(story, payload)
        story.append(PageBreak())

        if payload.magnet_metrics is not None:
            geometry_images = self._find_geometry_images(payload.studies)
            self._append_magnet_data(story, payload.magnet_metrics, geometry_images)
            story.append(Spacer(1, 0.25 * cm))

        self._append_bh_curves(story, payload.studies)
        story.append(PageBreak())

        self._append_bfield_results(
            story,
            payload.studies,
            payload.summary_labels,
            payload.summary_parameters,
            payload.label_comments,
            payload.label_expected_ppms,
        )
        story.append(PageBreak())

        self._append_magnet_results(story, payload.studies, payload.summary_parameters)

        try:
            doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        finally:
            self._cleanup_temp_images()

    def generate_markdown(self, payload: ReportPayload) -> None:
        out_path = payload.output_path
        lines: list[str] = []

        title = "Magnetic Simulation Report Generator"
        subtitle = ""
        if payload.magnet_metrics is not None:
            title = payload.magnet_metrics.project or title
            subtitle = payload.magnet_metrics.magnet_characteristics or Path(payload.magnet_metrics.txt_path).name

        lines.append(f"# {title}")
        lines.append("")
        if subtitle:
            lines.append(f"### {subtitle}")
            lines.append("")

        lines.extend(self._build_markdown_index(payload))
        lines.append("")

        if payload.magnet_metrics is not None:
            lines.extend(self._build_markdown_magnet_data(payload.magnet_metrics, self._find_geometry_images(payload.studies), out_path))
            lines.append("")

        lines.extend(self._build_markdown_bh_curves(payload.studies, out_path))
        lines.append("")

        lines.extend(
            self._build_markdown_bfield_results(
                payload.studies,
                payload.summary_labels,
                payload.summary_parameters,
                payload.label_comments,
                payload.label_expected_ppms,
                out_path,
            )
        )
        lines.append("")
        lines.extend(self._build_markdown_magnet_results(payload.studies, payload.summary_parameters, out_path))
        lines.append("")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")

    def _append_magnet_data(self, story: list, metrics: MagnetMetrics, geometry_images: list[Path]) -> None:
        story.append(self._anchored_heading("magnet-data", "Magnet Data", self.h1))
        story.append(Spacer(1, 0.2 * cm))

        rows = [
            ["Project", metrics.project],
            ["COMSOL Version", metrics.comsol_version],
            ["Date", metrics.run_date],
            ["Original TXT", self._p(metrics.txt_path)],
            ["Number of magnets", str(metrics.n_magnets)],
            ["Number of rings", str(metrics.n_rings)],
            ["Br (T)", self._fmt(metrics.br_t)],
            ["Magnet size (mm^3)", metrics.magnet_size_mm3],
            ["Magnet length (mm)", self._fmt(metrics.magnet_length_mm)],
            ["Y_length", self._fmt_mm_range(metrics.y_length_min_mm, metrics.y_length_max_mm)],
            ["Z_length", self._fmt_mm_range(metrics.z_length_min_mm, metrics.z_length_max_mm)],
            ["InterRing distance", self._fmt(metrics.interring_distance_mm) if metrics.interring_distance_mm is not None else metrics.interring_note],
            ["Expected ppm", self._fmt(metrics.expected_ppm) if metrics.expected_ppm is not None else "N/A"],
            ["Other information", self._p(metrics.other_information if metrics.other_information else "N/A")],
        ]
        table = Table(rows, colWidths=[5 * cm, 11.5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF3FA")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C4D3E0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        expected_row_index = next((idx for idx, row in enumerate(rows) if row[0] == "Expected ppm"), None)
        if expected_row_index is not None:
            table.setStyle(TableStyle([("FONTNAME", (0, expected_row_index), (-1, expected_row_index), "Helvetica-Bold")]))
        story.append(table)
        story.append(Spacer(1, 0.3 * cm))

        if metrics.other_info_images:
            self._append_attached_images(story, metrics.other_info_images)
            story.append(Spacer(1, 0.15 * cm))

        self._append_geometry_images_row(story, geometry_images)

        story.append(Paragraph("Rings", self.h2))
        ring_rows = [["Ring", "X position (mm)", "Magnets"]]
        for ring in metrics.rings:
            ring_rows.append([str(ring.ring_index), self._fmt(ring.x_position_mm), str(ring.magnets)])
        ring_table = Table(ring_rows, colWidths=[3 * cm, 6 * cm, 3 * cm])
        ring_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDEAF7")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B5C6D7")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        story.append(ring_table)

    def _append_index(self, story: list, payload: ReportPayload) -> None:
        story.append(self._anchored_heading("index", "Index", self.h1))
        entries: list[tuple[int, str, str]] = [
            (0, "1. Magnet data", "magnet-data"),
            (0, "2. BH curves", "bh-curves"),
        ]

        for study_index, study in enumerate(payload.studies, start=1):
            study_anchor = self._bh_study_anchor(study.folder_name)
            entries.append((1, f"2.{study_index} {study.folder_name}", study_anchor))

        entries.append((0, "3. Simulation B_field results", "simulation-bfield-results"))

        fov_label = self._preferred_bfield_label(payload.studies, payload.summary_labels)
        if fov_label:
            fov_anchor = self._label_anchor(fov_label)
            entries.append((1, f"3.1 {fov_label}", fov_anchor))
            entries.append((2, "3.1.1 Table summary", f"{fov_anchor}-table"))
            entries.append((2, "3.1.2 Plots", f"{fov_anchor}-plots"))
            for study_index, study in enumerate(payload.studies, start=1):
                entries.append((3, f"3.1.2.{study_index} {study.folder_name}", f"{fov_anchor}-plots-{study_index}"))
        else:
            entries.append((1, "3.1 FOV", "simulation-bfield-results"))

        entries.append((0, "4. Simulation Magnet results", "simulation-magnet-results"))
        entries.append((1, "4.1 Table summary", "simulation-magnet-results-table"))
        entries.append((1, "4.2 Plots", "simulation-magnet-results-plots"))
        for study_index, study in enumerate(payload.studies, start=1):
            entries.append((2, f"4.2.{study_index} {study.folder_name}", f"magnet-plots-{study_index}"))

        for indent, entry, anchor in entries:
            spacer = "&nbsp;" * (indent * 6)
            story.append(Paragraph(f'{spacer}<a href="#{anchor}" color="blue">{escape(entry)}</a>', self.normal))

    def _append_bfield_results(
        self,
        story: list,
        studies: list[SimulationStudyResult],
        selected_labels: list[str],
        selected_parameters: list[str],
        label_comments: dict[str, str],
        label_expected_ppms: dict[str, str],
    ) -> None:
        story.append(self._anchored_heading("simulation-bfield-results", "Simulation B_field results", self.h1))
        parent_path = self._common_parent_path(studies)
        if parent_path:
            story.append(Paragraph(f"Path: {escape(parent_path)}", self.cell))
            story.append(Spacer(1, 0.1 * cm))

        fov_label = self._preferred_bfield_label(studies, selected_labels)
        if not fov_label:
            story.append(Paragraph("No selected FOV histogram label available for the chosen studies.", self.normal))
            return

        label_anchor = self._label_anchor(fov_label)
        story.append(Spacer(1, 0.2 * cm))
        story.append(self._anchored_heading(label_anchor, fov_label, self.h2))
        comment = label_comments.get(fov_label, "").strip()
        if comment:
            story.append(Paragraph(f'Details: "{escape(comment)}"', self.cell))
        expected_ppm = label_expected_ppms.get(fov_label, "").strip()
        if expected_ppm:
            story.append(Paragraph(f'Expected ppms: {escape(expected_ppm)}', self.cell))

        story.append(self._anchored_heading(f"{label_anchor}-table", "Table summary", self.h3))
        table = self._build_summary_table_for_label(studies, fov_label, selected_parameters)
        story.append(table)

        story.append(self._anchored_heading(f"{label_anchor}-plots", "Plots", self.h3))
        self._append_bfield_label_plots(story, studies, fov_label)

    def _append_magnet_results(self, story: list, studies: list[SimulationStudyResult], selected_parameters: list[str]) -> None:
        story.append(self._anchored_heading("simulation-magnet-results", "Simulation Magnet results", self.h1))
        story.append(self._anchored_heading("simulation-magnet-results-table", "Table summary", self.h2))
        magnet_table = self._build_magnet_summary_table(studies)
        story.append(magnet_table)

        story.append(self._anchored_heading("simulation-magnet-results-plots", "Plots", self.h2))
        for study_index, study in enumerate(studies, start=1):
            story.append(self._anchored_heading(f"magnet-plots-{study_index}", study.folder_name, self.h3))
            self._append_magnet_only_plots(story, study)

    def _append_bh_curves(self, story: list, studies: list[SimulationStudyResult]) -> None:
        story.append(self._anchored_heading("bh-curves", "BH curves", self.h1))

        if not studies:
            story.append(Paragraph("No simulation studies selected.", self.normal))
            return

        for study in studies:
            story.append(self._anchored_heading(self._bh_study_anchor(study.folder_name), study.folder_name, self.h2))

            material = study.material_curve
            material_name = material.name if material is not None and material.name else study.material_name
            if material_name:
                story.append(Paragraph(f"Material used: {escape(material_name)}", self.cell))
            else:
                story.append(Paragraph("Material used: N/A", self.cell))

            story.append(self._anchored_heading(f"{self._bh_study_anchor(study.folder_name)}-material", f"Material: {material_name or 'N/A'}", self.h3))
            self._append_material_details(story, material, heading="BH curve")
            story.append(Spacer(1, 0.1 * cm))

    def _build_summary_table_for_label(
        self,
        studies: list[SimulationStudyResult],
        label: str,
        selected_parameters: list[str],
    ) -> Table:
        selected = [s for s in studies if label in s.histogram_metrics]
        if not selected:
            return Table([["No data"]])

        header_row_1 = ["Parameter", "Unit"]
        header_row_2 = ["", ""]
        col_widths = [3.8 * cm, 1.6 * cm]
        for study in selected:
            header_row_1.append(study.folder_name)
            header_row_2.append("Value")
            col_widths.append(4.2 * cm)

        rows = [header_row_1, header_row_2]
        params_with_group = [
            ("P2P ppm", "group1"),
            ("Bmin", "group1"),
            ("Bmax", "group1"),
            ("Bavg", "group1"),
            ("1-99% ppm", "group2"),
            ("P1", "group2"),
            ("P99", "group2"),
            ("5-95% ppm", "group3"),
            ("P5", "group3"),
            ("P95", "group3"),
            ("Peak", "group4"),
        ]
        if selected_parameters:
            params_with_group = [item for item in params_with_group if item[0] in selected_parameters]
        if not params_with_group:
            return Table([["No selected rows"]])

        group_rows: list[tuple[int, str]] = []
        for parameter, group in params_with_group:
            mt_unit = "ppm" if "ppm" in parameter else "mT"
            mt_row = [parameter, mt_unit]
            khz_row = ["", "kHz"]
            for study in selected:
                metrics = study.histogram_metrics[label]
                b_val, f_val = self._summary_values(metrics, parameter)
                mt_row.append(self._fmt3(b_val))
                khz_row.append(self._fmt3(f_val))
            row_start = len(rows)
            rows.append(mt_row)
            rows.append(khz_row)
            group_rows.append((row_start, group))

        table = Table(rows, colWidths=col_widths)
        style = [
            ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#DDEAF7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B5C6D7")),
            ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]

        # Merge parameter cell over its mT/kHz rows.
        for row_start, _ in group_rows:
            style.append(("SPAN", (0, row_start), (0, row_start + 1)))
            style.append(("FONTNAME", (0, row_start), (0, row_start), "Helvetica-Bold"))

        ppm_parameters = {"P2P ppm", "1-99% ppm", "5-95% ppm"}
        for row_start, (parameter, _) in zip([row for row, _ in group_rows], params_with_group):
            if parameter in ppm_parameters:
                style.append(("FONTNAME", (0, row_start), (-1, row_start), "Helvetica-Bold"))

        # Apply grouped coloring per requested parameter blocks.
        group_colors = {
            "group1": colors.HexColor("#EAF3FF"),
            "group2": colors.HexColor("#EAFCEF"),
            "group3": colors.HexColor("#FFF7E8"),
            "group4": colors.HexColor("#FFECEC"),
        }
        for row_start, group in group_rows:
            fill = group_colors[group]
            style.append(("BACKGROUND", (0, row_start), (-1, row_start + 1), fill))

        # Keep unit cells visually distinct.
        for row_idx in range(2, len(rows)):
            style.append(("BACKGROUND", (1, row_idx), (1, row_idx), colors.HexColor("#F7FAFE")))

        table.setStyle(TableStyle(style))
        return table

    def _build_magnet_summary_table(self, studies: list[SimulationStudyResult]) -> Table:
        data = self._magnet_summary_table_content(studies)
        if not data:
            return Table([["No magnet histogram summary data"]])

        col_count = len(data[0])
        if col_count <= 1:
            col_widths = [16.2 * cm]
        else:
            remaining_width = 16.2 - 3.2
            other_col_width = remaining_width / (col_count - 1)
            col_widths = [3.2 * cm] + [other_col_width * cm] * (col_count - 1)

        table = Table(data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDEAF7")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B5C6D7")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return table

    def _magnet_summary_table_content(self, studies: list[SimulationStudyResult]) -> list[list[str]]:
        header = ["Simulation", "<98%", "<95%", "<90%", "<85%", "WDV", "M_min", "M_max", "Br"]
        simulation_rows: list[list[str]] = []

        for study in studies:
            summary = study.magnet_histogram_summary
            if summary is None:
                continue

            simulation_rows.append(
                [
                    study.folder_name,
                    f"{summary.lt_98_pct:.1f}%",
                    f"{summary.lt_95_pct:.1f}%",
                    f"{summary.lt_90_pct:.1f}%",
                    f"{summary.lt_85_pct:.1f}%",
                    f"{summary.wdv:.2f}",
                    f"{summary.m_min_t:.3f} T ({summary.m_min_pct:.1f}%)",
                    f"{summary.m_max_t:.3f} T ({summary.m_max_pct:.1f}%)",
                    f"{summary.br_t:.3f} T (100%)",
                ]
            )

        if not simulation_rows:
            return []

        source = [header] + simulation_rows
        transposed: list[list[str]] = []
        for col_idx in range(len(header)):
            transposed.append([source[row_idx][col_idx] for row_idx in range(len(source))])
        return transposed

    def _summary_values(self, metrics: dict[str, float], parameter: str) -> tuple[float, float]:
        gamma_khz_per_mt = 42.58
        peak = float(metrics.get("Peak", 0.0))

        if parameter == "P2P ppm":
            bw = float(metrics.get("BW_p2p_Hz", 0.0))
            if bw == 0.0:
                bw = (float(metrics.get("B_max", 0.0)) - float(metrics.get("B_min", 0.0))) * gamma_khz_per_mt * 1000.0
            return float(metrics.get("P2P ppm", 0.0)), bw / 1000.0
        if parameter == "Bmin":
            b = float(metrics.get("B_min", 0.0))
            return b, (b - peak) * gamma_khz_per_mt
        if parameter == "Bmax":
            b = float(metrics.get("B_max", 0.0))
            return b, (b - peak) * gamma_khz_per_mt
        if parameter == "Bavg":
            b = float(metrics.get("B_avg", 0.0))
            return b, (b - peak) * gamma_khz_per_mt
        if parameter == "1-99% ppm":
            bw = float(metrics.get("BW_1_99_Hz", 0.0))
            if bw == 0.0:
                bw = (float(metrics.get("P99", 0.0)) - float(metrics.get("P1", 0.0))) * gamma_khz_per_mt * 1000.0
            return float(metrics.get("1-99% ppm", 0.0)), bw / 1000.0
        if parameter == "P1":
            b = float(metrics.get("P1", 0.0))
            return b, (b - peak) * gamma_khz_per_mt
        if parameter == "P99":
            b = float(metrics.get("P99", 0.0))
            return b, (b - peak) * gamma_khz_per_mt
        if parameter == "5-95% ppm":
            bw = float(metrics.get("BW_5_95_Hz", 0.0))
            if bw == 0.0:
                bw = (float(metrics.get("P95", 0.0)) - float(metrics.get("P5", 0.0))) * gamma_khz_per_mt * 1000.0
            return float(metrics.get("5-95% ppm", 0.0)), bw / 1000.0
        if parameter == "P5":
            b = float(metrics.get("P5", 0.0))
            return b, (b - peak) * gamma_khz_per_mt
        if parameter == "P95":
            b = float(metrics.get("P95", 0.0))
            return b, (b - peak) * gamma_khz_per_mt
        if parameter == "Peak":
            b = peak
            return b, 0.0
        return 0.0, 0.0

    def _append_bfield_label_plots(self, story: list, studies: list[SimulationStudyResult], label: str) -> None:
        found = False
        for study_index, study in enumerate(studies, start=1):
            domain = next((domain for domain in study.domains if domain.name == label), None)
            if domain is None:
                continue
            found = True
            story.append(self._anchored_heading(f"{self._label_anchor(label)}-plots-{study_index}", study.folder_name, self.study_title))
            self._append_domain_pair(story, domain.plot_3d, domain.histogram)
            self._append_projection_row_pdf(story, domain.projection_xy, domain.projection_yz, domain.projection_xz)
            self._append_optional_image(story, "Custom Coordinates", domain.custom_coordinates)
        if not found:
            story.append(Paragraph("No plots found.", self.normal))

    def _append_magnet_only_plots(self, story: list, study: SimulationStudyResult) -> None:
        self._append_domain_pair(story, study.magnets.plot_3d, study.magnets.histogram)
        self._append_projection_row_pdf(
            story,
            study.magnets.projection_xy,
            study.magnets.projection_yz,
            study.magnets.projection_xz,
        )

    @staticmethod
    def _common_parent_path(studies: list[SimulationStudyResult]) -> str:
        if not studies:
            return ""
        parents = [str(Path(study.folder_path).parent) for study in studies]
        try:
            return os.path.commonpath(parents)
        except Exception:
            return parents[0]

    @staticmethod
    def _selected_summary_labels(payload: ReportPayload) -> list[str]:
        labels = sorted({label for study in payload.studies for label in study.histogram_metrics.keys()})
        if payload.summary_labels:
            labels = [label for label in labels if label in payload.summary_labels]
        return labels

    @staticmethod
    def _selected_summary_labels_from_studies(studies: list[SimulationStudyResult], selected_labels: list[str]) -> list[str]:
        labels = sorted({label for study in studies for label in study.histogram_metrics.keys()})
        if selected_labels:
            labels = [label for label in labels if label in selected_labels]
        return labels

    @staticmethod
    def _preferred_bfield_label(studies: list[SimulationStudyResult], selected_labels: list[str]) -> str | None:
        labels = sorted({label for study in studies for label in study.histogram_metrics.keys()})
        if selected_labels:
            labels = [label for label in labels if label in selected_labels]
        if not labels:
            return None

        for candidate in labels:
            low = candidate.lower().strip()
            if low in {"fov", "b_fov", "bfov"}:
                return candidate
        return labels[0]

    def _find_geometry_images(self, studies: list[SimulationStudyResult]) -> list[Path]:
        geometry: list[Path] = []
        seen: set[Path] = set()
        roots_seen: set[Path] = set()

        for study in studies:
            study_path = Path(study.folder_path)
            parent = study_path.parent
            candidates = [parent]
            if parent.name.lower() != "simulation_results":
                candidates.append(parent / "Simulation_results")

            simulation_root = next((candidate for candidate in candidates if candidate.exists() and candidate.is_dir() and candidate.name.lower() == "simulation_results"), None)
            if simulation_root is None:
                continue

            try:
                resolved_root = simulation_root.resolve()
            except Exception:
                resolved_root = simulation_root

            if resolved_root in roots_seen:
                continue
            roots_seen.add(resolved_root)

            for png_path in simulation_root.glob("*.png"):
                if not png_path.name.lower().startswith("geometry"):
                    continue
                try:
                    resolved = png_path.resolve()
                except Exception:
                    resolved = png_path
                if resolved in seen:
                    continue
                seen.add(resolved)
                geometry.append(png_path)

        def order_key(path: Path) -> tuple[int, str]:
            name = path.name.lower()
            if name == "geometry_3d.png":
                return (0, name)
            if name == "geometry_xy.png":
                return (1, name)
            if name == "geometry_yz.png":
                return (2, name)
            return (3, name)

        geometry.sort(key=order_key)
        return geometry

    def _append_geometry_images_row(self, story: list, geometry_images: list[Path]) -> None:
        if not geometry_images:
            return

        normalized: list[Path] = []
        for image_path in geometry_images:
            normalized_path = self._prepare_image_for_pdf(image_path)
            if normalized_path is not None:
                normalized.append(normalized_path)

        if not normalized:
            return

        total_width = 16.2 * cm
        count = len(normalized)
        col_width = total_width / count
        cells = []
        for image_path in normalized:
            img = Image(str(image_path))
            img._restrictSize(max(1.0 * cm, col_width - 0.15 * cm), 6.4 * cm)
            cells.append(img)

        table = Table([cells], colWidths=[col_width] * count)
        table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 0.15 * cm))

    def _append_single_image_with_caption(
        self,
        story: list,
        image_path: Path,
        caption: str | None,
        width: float,
        height: float,
    ) -> None:
        normalized_path = self._prepare_image_for_pdf(image_path)
        if normalized_path is None:
            return
        img = Image(str(normalized_path))
        img._restrictSize(width, height)
        story.append(img)
        if caption:
            story.append(Paragraph(escape(caption), self.cell))
        story.append(Spacer(1, 0.15 * cm))

    def _append_domain_pair(self, story: list, plot3d_path: str | None, histogram_path: str | None) -> None:
        left = self._build_image_cell("3D Plot", plot3d_path)
        right = self._build_image_cell("Histogram", histogram_path)

        if left is None and right is None:
            return

        if left is not None and right is not None:
            table = Table([[left, right]], colWidths=[8.1 * cm, 8.1 * cm])
            table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(table)
            story.append(Spacer(1, 0.15 * cm))
            return

        single = left if left is not None else right
        table = Table([[single]], colWidths=[16.2 * cm])
        table.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (0, 0), "TOP")]))
        story.append(table)
        story.append(Spacer(1, 0.15 * cm))

    def _append_attached_images(self, story: list, image_infos: list[AttachedImageInfo]) -> None:
        cells = []
        for image_info in image_infos:
            path = Path(image_info.path)
            if not path.exists():
                continue
            normalized_path = self._prepare_image_for_pdf(path)
            if normalized_path is None:
                continue

            img = Image(str(normalized_path))
            img._restrictSize(7.8 * cm, 6.8 * cm)
            block: list = [img]
            if image_info.comment:
                block.extend([Spacer(1, 0.06 * cm), Paragraph(escape(image_info.comment), self.cell)])
            cells.append(block)

        if not cells:
            return

        row: list = []
        for idx, cell in enumerate(cells, start=1):
            row.append(cell)
            if idx % 2 == 0:
                table = Table([row], colWidths=[8.1 * cm, 8.1 * cm])
                table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story.append(table)
                story.append(Spacer(1, 0.15 * cm))
                row = []

        if row:
            table = Table([row], colWidths=[16.2 * cm])
            table.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (0, 0), "TOP")]))
            story.append(table)
            story.append(Spacer(1, 0.15 * cm))

    def _append_material_details(self, story: list, material: MaterialCurve | None, heading: str = "Material details") -> None:
        if material is None:
            return

        story.append(Spacer(1, 0.12 * cm))
        story.append(Paragraph(heading, self.h3))

        if material.comment:
            story.append(Paragraph(f"Comment: {escape(material.comment)}", self.cell))

        for link in material.links:
            story.append(self._material_link_paragraph(link))

        curve_rows = [["H (kA/m)", "B (T)"]]
        for h_val, b_val in material.points:
            curve_rows.append([self._fmt(h_val), self._fmt(b_val)])

        curve_table = Table(curve_rows, colWidths=[4.5 * cm, 4.5 * cm])
        curve_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDEAF7")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B5C6D7")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        story.append(curve_table)
        if material.images:
            story.append(Spacer(1, 0.12 * cm))
            story.append(Paragraph("Material images", self.normal))
            self._append_attached_images(story, material.images)

    def _material_link_paragraph(self, raw_link: str) -> Paragraph:
        href = escape(raw_link, quote=True)
        visible = escape(raw_link)
        return Paragraph(f"Reference link: <a href=\"{href}\" color=\"blue\">{visible}</a>", self.cell)

    def _anchored_heading(self, anchor: str, text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(f'<a name="{escape(anchor, quote=True)}"/>{escape(text)}', style)

    @staticmethod
    def _study_anchor(folder_name: str) -> str:
        return f"study-{folder_name.lower().replace(' ', '-')}"

    @staticmethod
    def _bh_study_anchor(folder_name: str) -> str:
        return f"bh-study-{folder_name.lower().replace(' ', '-')}"

    @staticmethod
    def _magnet_study_anchor(folder_name: str) -> str:
        return f"magnet-study-{folder_name.lower().replace(' ', '-')}"

    @staticmethod
    def _label_anchor(label: str) -> str:
        return f"summary-{label.lower().replace(' ', '-')}"

    def _build_image_cell(
        self,
        title: str,
        image_path: str | None,
        max_width_cm: float = 7.8,
        max_height_cm: float = 6.8,
    ):
        if not image_path:
            return None
        path = Path(image_path)
        if not path.exists():
            return None

        normalized_path = self._prepare_image_for_pdf(path)
        if normalized_path is None:
            return None

        img = Image(str(normalized_path))
        img._restrictSize(max_width_cm * cm, max_height_cm * cm)
        return [Paragraph(title, self.normal), Spacer(1, 0.08 * cm), img]

    def _append_optional_image(self, story: list, title: str, image_path: str | None) -> None:
        if not image_path:
            return
        path = Path(image_path)
        if not path.exists():
            return

        normalized_path = self._prepare_image_for_pdf(path)
        if normalized_path is None:
            return

        story.append(Paragraph(title, self.normal))
        img = Image(str(normalized_path))
        img._restrictSize(16.5 * cm, 8.2 * cm)
        story.append(img)
        story.append(Spacer(1, 0.15 * cm))

    def _append_projection_row_pdf(
        self,
        story: list,
        projection_xy: str | None,
        projection_yz: str | None,
        projection_xz: str | None,
    ) -> None:
        ordered = [("XY", projection_xy), ("YZ", projection_yz), ("XZ", projection_xz)]
        cells = []
        for title, path in ordered:
            cell = self._build_image_cell(title, path, max_width_cm=4.7, max_height_cm=3.6)
            if cell is not None:
                cells.append(cell)

        if not cells:
            return

        if len(cells) == 1:
            table = Table([[cells[0]]], colWidths=[16.2 * cm])
            table.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (0, 0), "TOP")]))
            story.append(table)
            story.append(Spacer(1, 0.15 * cm))
            return

        col_width = 16.2 * cm / len(cells)
        table = Table([cells], colWidths=[col_width] * len(cells))
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 0.15 * cm))

    def _fmt(self, value: float | None) -> str:
        if value is None:
            return ""
        rounded = round(float(value), 2)
        if abs(rounded - int(rounded)) < 1e-9:
            return str(int(rounded))
        return (f"{rounded:.2f}").rstrip("0").rstrip(".")

    def _fmt3(self, value: float | None) -> str:
        if value is None:
            return ""
        return f"{float(value):.3f}"

    def _fmt_mm_range(self, min_value: float, max_value: float) -> str:
        if abs(float(min_value) - float(max_value)) < 1e-9:
            return f"{self._fmt(max_value)} mm"
        return f"[{self._fmt(min_value)}, {self._fmt(max_value)}] mm"

    def _p(self, text: str) -> Paragraph:
        return Paragraph(escape(text), self.cell)

    def _prepare_image_for_pdf(self, source_path: Path) -> Path | None:
        try:
            source_for_open = self._to_windows_long_path_if_needed(source_path)
            with PILImage.open(source_for_open) as pil_img:
                if pil_img.mode not in ("RGB", "L"):
                    pil_img = pil_img.convert("RGB")

                temp_name = f"msr_{uuid.uuid4().hex}.png"
                temp_path = Path(tempfile.gettempdir()) / temp_name
                pil_img.save(temp_path, format="PNG")
                self._temp_image_paths.append(temp_path)
                return temp_path
        except Exception:
            return None

    def _to_windows_long_path_if_needed(self, path: Path) -> str:
        raw = str(path)
        if os.name != "nt":
            return raw

        normalized = str(path.resolve())
        if normalized.startswith("\\\\?\\"):
            return normalized

        # Enable long-path access for Windows paths beyond MAX_PATH.
        if len(normalized) >= 248:
            if normalized.startswith("\\\\"):
                return "\\\\?\\UNC\\" + normalized.lstrip("\\")
            return "\\\\?\\" + normalized

        return normalized

    def _cleanup_temp_images(self) -> None:
        for temp_path in self._temp_image_paths:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
        self._temp_image_paths = []

    def _build_markdown_index(self, payload: ReportPayload) -> list[str]:
        lines = ["## Index", ""]
        lines.append("- [1. Magnet data](#1-magnet-data)")
        lines.append("- [2. BH curves](#2-bh-curves)")

        for study_index, study in enumerate(payload.studies, start=1):
            lines.append(f"- [2.{study_index} {study.folder_name}](#2{study_index}-{self._slug(study.folder_name)})")

        lines.append("- [3. Simulation B_field results](#3-simulation-b_field-results)")

        fov_label = self._preferred_bfield_label(payload.studies, payload.summary_labels)
        if fov_label:
            lines.append(f"- [3.1 {fov_label}](#31-{self._slug(fov_label)})")
            lines.append("- [3.1.1 Table summary](#311-table-summary)")
            lines.append("- [3.1.2 Plots](#312-plots)")
            for study_index, study in enumerate(payload.studies, start=1):
                lines.append(f"- [3.1.2.{study_index} {study.folder_name}](#312{study_index}-{self._slug(study.folder_name)})")

        lines.append("- [4. Simulation Magnet results](#4-simulation-magnet-results)")
        lines.append("- [4.1 Table summary](#41-table-summary)")
        lines.append("- [4.2 Plots](#42-plots)")
        for study_index, study in enumerate(payload.studies, start=1):
            lines.append(f"- [4.2.{study_index} {study.folder_name}](#42{study_index}-{self._slug(study.folder_name)})")
        return lines

    def _build_markdown_magnet_data(self, metrics: MagnetMetrics, geometry_images: list[Path], out_path: Path) -> list[str]:
        lines = ["## 1. Magnet data", ""]
        rows = [
            ("Project", metrics.project),
            ("COMSOL Version", metrics.comsol_version),
            ("Date", metrics.run_date),
            ("Original TXT", metrics.txt_path),
            ("Number of magnets", str(metrics.n_magnets)),
            ("Number of rings", str(metrics.n_rings)),
            ("Br (T)", self._fmt(metrics.br_t)),
            ("Magnet size (mm^3)", metrics.magnet_size_mm3),
            ("Magnet length (mm)", self._fmt(metrics.magnet_length_mm)),
            ("Y_length", self._fmt_mm_range(metrics.y_length_min_mm, metrics.y_length_max_mm)),
            ("Z_length", self._fmt_mm_range(metrics.z_length_min_mm, metrics.z_length_max_mm)),
            ("InterRing distance", self._fmt(metrics.interring_distance_mm) if metrics.interring_distance_mm is not None else metrics.interring_note),
            ("Expected ppm", self._fmt(metrics.expected_ppm) if metrics.expected_ppm is not None else "N/A"),
            ("Other information", metrics.other_information if metrics.other_information else "N/A"),
        ]
        lines.extend(["| Field | Value |", "|---|---|"])
        for key, value in rows:
            lines.append(f"| {key} | {self._escape_md(value)} |")
        lines.append("")

        if metrics.other_info_images:
            lines.append("### Other information images")
            lines.extend(self._md_image_grid([(None, item.path, item.comment) for item in metrics.other_info_images], out_path, columns=2))
            lines.append("")

        if geometry_images:
            lines.append("### Geometry")
            lines.extend(self._md_image_grid([(None, str(path), "") for path in geometry_images], out_path, columns=max(1, len(geometry_images))))
            lines.append("")

        lines.append("### Rings")
        lines.extend(["| Ring | X position (mm) | Magnets |", "|---:|---:|---:|"])
        for ring in metrics.rings:
            lines.append(f"| {ring.ring_index} | {self._fmt(ring.x_position_mm)} | {ring.magnets} |")
        return lines

    def _build_markdown_bh_curves(self, studies: list[SimulationStudyResult], out_path: Path) -> list[str]:
        lines = ["## 2. BH curves", ""]
        if not studies:
            lines.append("No simulation studies selected.")
            return lines

        for study in studies:
            lines.append(f"### {study.folder_name}")
            material = study.material_curve
            material_name = material.name if material is not None and material.name else study.material_name
            lines.append(f"#### Material: {material_name or 'N/A'}")
            lines.append("")
            lines.append(f"Material used: {self._escape_md(material_name or 'N/A')}")
            lines.append("")
            lines.extend(self._build_markdown_material_details(material, out_path))
            lines.append("")
        return lines

    def _build_markdown_material_details(self, material: MaterialCurve | None, out_path: Path) -> list[str]:
        if material is None:
            return ["No material details available."]

        lines: list[str] = []
        if material.comment:
            lines.append(f"Comment: {self._escape_md(material.comment)}")
        for link in material.links:
            lines.append(f"Reference link: [{self._escape_md(link)}]({link})")
        lines.append("")

        lines.extend(["| H (kA/m) | B (T) |", "|---:|---:|"])
        for h_val, b_val in material.points:
            lines.append(f"| {self._fmt(h_val)} | {self._fmt(b_val)} |")

        if material.images:
            lines.append("")
            lines.append("Material images")
            lines.extend(self._md_image_grid([(None, item.path, item.comment) for item in material.images], out_path, columns=2))
        return lines

    def _build_markdown_bfield_results(
        self,
        studies: list[SimulationStudyResult],
        selected_labels: list[str],
        selected_parameters: list[str],
        label_comments: dict[str, str],
        label_expected_ppms: dict[str, str],
        out_path: Path,
    ) -> list[str]:
        lines = ["## 3. Simulation B_field results", ""]
        parent_path = self._common_parent_path(studies)
        if parent_path:
            lines.append(f"Path: {self._escape_md(parent_path)}")
            lines.append("")

        fov_label = self._preferred_bfield_label(studies, selected_labels)
        if not fov_label:
            lines.append("No selected FOV histogram label available for the chosen studies.")
            return lines

        lines.append(f"### 3.1 {fov_label}")
        comment = label_comments.get(fov_label, "").strip()
        if comment:
            lines.append(f"Details: \"{self._escape_md(comment)}\"")
        expected_ppm = label_expected_ppms.get(fov_label, "").strip()
        if expected_ppm:
            lines.append(f"Expected ppms: {self._escape_md(expected_ppm)}")
        lines.append("")
        lines.append("#### 3.1.1 Table summary")
        lines.extend(self._build_markdown_summary_table(studies, fov_label, selected_parameters))
        lines.append("")
        lines.append("#### 3.1.2 Plots")
        lines.extend(self._build_markdown_bfield_plots(studies, fov_label, out_path))
        lines.append("")
        return lines

    def _build_markdown_summary_table(self, studies: list[SimulationStudyResult], label: str, selected_parameters: list[str]) -> list[str]:
        selected = [s for s in studies if label in s.histogram_metrics]
        if not selected:
            return ["No data"]

        params = [
            "P2P ppm",
            "Bmin",
            "Bmax",
            "Bavg",
            "1-99% ppm",
            "P1",
            "P99",
            "5-95% ppm",
            "P5",
            "P95",
            "Peak",
        ]
        if selected_parameters:
            params = [p for p in params if p in selected_parameters]
        if not params:
            return ["No selected rows"]

        header = ["Parameter", "Unit"] + [s.folder_name for s in selected]
        lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
        for parameter in params:
            mt_row = [parameter, "ppm" if "ppm" in parameter else "mT"]
            khz_row = ["", "kHz"]
            for study in selected:
                b_val, f_val = self._summary_values(study.histogram_metrics[label], parameter)
                mt_row.append(self._fmt3(b_val))
                khz_row.append(self._fmt3(f_val))
            lines.append("| " + " | ".join(mt_row) + " |")
            lines.append("| " + " | ".join(khz_row) + " |")
        return lines

    def _build_markdown_bfield_plots(self, studies: list[SimulationStudyResult], label: str, out_path: Path) -> list[str]:
        lines: list[str] = []
        found = False
        for study in studies:
            domain = next((domain for domain in study.domains if domain.name == label), None)
            if domain is None:
                continue
            found = True
            lines.append(f"{study.folder_name}")
            lines.extend(
                self._md_image_grid(
                    [("3D Plot", domain.plot_3d, ""), ("Histogram", domain.histogram, "")],
                    out_path,
                    columns=2,
                )
            )
            lines.extend(
                self._md_image_grid(
                    [("XY", domain.projection_xy, ""), ("YZ", domain.projection_yz, ""), ("XZ", domain.projection_xz, "")],
                    out_path,
                    columns=3,
                )
            )
            if domain.custom_coordinates:
                lines.extend(self._md_image_grid([("Custom Coordinates", domain.custom_coordinates, "")], out_path, columns=1))
        if not found:
            lines.append("No plots found.")
        return lines

    def _build_markdown_magnet_results(self, studies: list[SimulationStudyResult], selected_parameters: list[str], out_path: Path) -> list[str]:
        lines = ["## 4. Simulation Magnet results", ""]
        lines.append("### 4.1 Table summary")
        lines.extend(self._build_markdown_magnet_summary_table(studies))
        lines.append("")
        lines.append("### 4.2 Plots")
        for study_index, study in enumerate(studies, start=1):
            lines.append(f"#### 4.2.{study_index} {study.folder_name}")
            lines.extend(
                self._md_image_grid(
                    [("3D Plot", study.magnets.plot_3d, ""), ("Histogram", study.magnets.histogram, "")],
                    out_path,
                    columns=2,
                )
            )
            lines.extend(
                self._md_image_grid(
                    [("XY", study.magnets.projection_xy, ""), ("YZ", study.magnets.projection_yz, ""), ("XZ", study.magnets.projection_xz, "")],
                    out_path,
                    columns=3,
                )
            )
            lines.append("")
        return lines

    def _build_markdown_magnet_summary_table(self, studies: list[SimulationStudyResult]) -> list[str]:
        data = self._magnet_summary_table_content(studies)
        if not data:
            return ["No magnet histogram summary data."]

        header = data[0]
        rows = data[1:]
        lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
        for row in rows:
            lines.append("| " + " | ".join(self._escape_md(value) for value in row) + " |")
        return lines

    def _md_image_grid(self, entries: list[tuple[str | None, str | None, str]], out_path: Path, columns: int) -> list[str]:
        valid: list[tuple[str, str, str]] = []
        for title, path, caption in entries:
            if not path:
                continue
            p = Path(path)
            if not p.exists():
                continue
            valid.append((title or "", self._md_image_path(p, out_path), caption))

        if not valid:
            return []

        cells = []
        for title, image_ref, caption in valid:
            title_html = f"<div><strong>{escape(title)}</strong></div>" if title else ""
            caption_html = f"<div>{escape(caption)}</div>" if caption else ""
            cells.append(f"<td align=\"center\" valign=\"top\">{title_html}<img src=\"{escape(image_ref, quote=True)}\" style=\"max-width:100%; height:auto;\"/>{caption_html}</td>")

        row_cells = cells[:columns]
        lines = ["<table><tr>" + "".join(row_cells) + "</tr></table>"]

        if len(cells) > columns:
            remaining = cells[columns:]
            for idx in range(0, len(remaining), columns):
                lines.append("<table><tr>" + "".join(remaining[idx : idx + columns]) + "</tr></table>")
        return lines

    @staticmethod
    def _escape_md(text: str) -> str:
        return str(text).replace("|", "\\|").replace("\n", " ")

    @staticmethod
    def _slug(text: str) -> str:
        return text.strip().lower().replace(" ", "-")

    @staticmethod
    def _md_image_path(image_path: Path, out_path: Path) -> str:
        try:
            return str(image_path.resolve().relative_to(out_path.parent.resolve())).replace("\\", "/")
        except Exception:
            return str(image_path.resolve()).replace("\\", "/")

    @staticmethod
    def _add_page_number(canvas, doc) -> None:
        page_num = canvas.getPageNumber()
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(19.5 * cm, 1.2 * cm, f"Page {page_num}")
