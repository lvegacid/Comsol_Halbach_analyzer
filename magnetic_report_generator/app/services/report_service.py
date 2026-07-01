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

    def generate_pdf(self, payload: ReportPayload) -> None:
        self._temp_image_paths = []
        doc = SimpleDocTemplate(
            str(payload.output_pdf),
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

        self._append_bfield_results(
            story,
            payload.studies,
            payload.summary_labels,
            payload.summary_parameters,
            payload.label_comments,
        )
        story.append(PageBreak())

        self._append_magnet_results(story, payload.studies)

        try:
            doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        finally:
            self._cleanup_temp_images()

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
            ["Major ellipse side (mm)", f"{self._fmt(metrics.major_ellipse_side_mm)} ({metrics.major_axis_direction})"],
            ["Minor ellipse side (mm)", f"{self._fmt(metrics.minor_ellipse_side_mm)} ({metrics.minor_axis_direction})"],
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

        for image_path in geometry_images:
            self._append_single_image_with_caption(story, image_path, None, 16.5 * cm, 8.2 * cm)

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
            (0, "2. Simulation B_field results", "simulation-bfield-results"),
        ]

        summary_labels = self._selected_summary_labels(payload)
        for label_index, label in enumerate(summary_labels, start=1):
            label_anchor = self._label_anchor(label)
            entries.append((1, f"2.{label_index} {label}", label_anchor))
            entries.append((2, f"2.{label_index}.1 Table summary", f"{label_anchor}-table"))
            entries.append((2, f"2.{label_index}.2 Plots", f"{label_anchor}-plots"))

        entries.append((0, "3. Simulation Magnet results", "simulation-magnet-results"))
        for study_index, study in enumerate(payload.studies, start=1):
            study_anchor = self._study_anchor(study.folder_name)
            entries.append((1, f"3.{study_index} {study.folder_name}", study_anchor))
            entries.append((2, f"3.{study_index}.1 Plots", f"{study_anchor}-plots"))

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
    ) -> None:
        story.append(self._anchored_heading("simulation-bfield-results", "Simulation B_field results", self.h1))
        parent_path = self._common_parent_path(studies)
        if parent_path:
            story.append(Paragraph(f"Path: {escape(parent_path)}", self.cell))
            story.append(Spacer(1, 0.1 * cm))
        labels = self._selected_summary_labels_from_studies(studies, selected_labels)
        if not labels:
            story.append(Paragraph("No selected histogram labels available for the chosen studies.", self.normal))
            return

        for label in labels:
            story.append(Spacer(1, 0.2 * cm))
            story.append(self._anchored_heading(self._label_anchor(label), label, self.h2))
            comment = label_comments.get(label, "").strip()
            if comment:
                story.append(Paragraph(f'Details: "{escape(comment)}"', self.cell))
            story.append(self._anchored_heading(f"{self._label_anchor(label)}-table", "Table summary", self.h3))
            table = self._build_summary_table_for_label(studies, label, selected_parameters)
            story.append(table)
            story.append(self._anchored_heading(f"{self._label_anchor(label)}-plots", "Plots", self.h3))
            self._append_bfield_label_plots(story, studies, label)

    def _append_magnet_results(self, story: list, studies: list[SimulationStudyResult]) -> None:
        story.append(self._anchored_heading("simulation-magnet-results", "Simulation Magnet results", self.h1))
        for study in studies:
            story.append(self._anchored_heading(self._study_anchor(study.folder_name), study.folder_name, self.h2))
            story.append(self._anchored_heading(f"{self._study_anchor(study.folder_name)}-plots", "Plots", self.h3))
            self._append_magnet_only_plots(story, study)

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
        for study in studies:
            domain = next((domain for domain in study.domains if domain.name == label), None)
            if domain is None:
                continue
            found = True
            story.append(Paragraph(f"{study.folder_name}", self.normal))
            self._append_domain_pair(story, domain.plot_3d, domain.histogram)
            self._append_optional_image(story, "Custom Coordinates", domain.custom_coordinates)
        if not found:
            story.append(Paragraph("No plots found.", self.normal))

    def _append_magnet_only_plots(self, story: list, study: SimulationStudyResult) -> None:
        self._append_domain_pair(story, study.magnets.plot_3d, study.magnets.histogram)

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

    def _find_geometry_images(self, studies: list[SimulationStudyResult]) -> list[Path]:
        geometry: list[Path] = []
        seen: set[Path] = set()
        for study in studies:
            candidate = Path(study.folder_path).parent / "Geometry.png"
            if candidate.exists():
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    geometry.append(candidate)
        return geometry

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

    def _append_material_details(self, story: list, material: MaterialCurve | None) -> None:
        if material is None:
            return

        story.append(Spacer(1, 0.12 * cm))
        story.append(Paragraph("Material details", self.h3))

        if material.comment:
            story.append(Paragraph(f"Comment: {escape(material.comment)}", self.cell))

        if material.link:
            story.append(self._material_link_paragraph(material.link))

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
    def _label_anchor(label: str) -> str:
        return f"summary-{label.lower().replace(' ', '-')}"

    def _build_image_cell(self, title: str, image_path: str | None):
        if not image_path:
            return None
        path = Path(image_path)
        if not path.exists():
            return None

        normalized_path = self._prepare_image_for_pdf(path)
        if normalized_path is None:
            return None

        img = Image(str(normalized_path))
        img._restrictSize(7.8 * cm, 6.8 * cm)
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

    @staticmethod
    def _add_page_number(canvas, doc) -> None:
        page_num = canvas.getPageNumber()
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(19.5 * cm, 1.2 * cm, f"Page {page_num}")
