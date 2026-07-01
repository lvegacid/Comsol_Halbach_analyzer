# Magnetic Simulation Report Generator

Standalone desktop application for building professional magnetic simulation PDF reports.

## Stack

- Python 3.11+
- PySide6
- pandas
- numpy
- reportlab
- Pillow
- JSON persistent settings

## Project Architecture

- `main.py`: Application entrypoint.
- `app/gui/main_window.py`: Main window, tab orchestration, state sync, PDF actions.
- `app/gui/tabs/magnet_data_tab.py`: Tab 1, TXT loading and magnet data computation display.
- `app/gui/tabs/simulation_results_tab.py`: Tab 2, folder scan, study selection, symmetry/material setup, material DB controls.
- `app/gui/tabs/preview_tab.py`: Tab 3, report preview text.
- `app/gui/tabs/generate_tab.py`: Tab 4, generate/export actions.
- `app/gui/dialogs/material_dialog.py`: Material editor dialog (H/B table add/delete/edit).
- `app/services/magnet_data_service.py`: TXT parsing and derived metrics.
- `app/services/simulation_service.py`: Study folder discovery and PNG grouping logic.
- `app/services/report_service.py`: ReportLab PDF generation (tables, titles, images, page numbers).
- `app/services/settings_service.py`: Persistent JSON settings and material database.
- `app/models/entities.py`: Dataclasses and typed shared entities.

## Persistent Storage

Stored in:

- `~/.magnetic_sim_report_generator/settings.json`
- `~/.magnetic_sim_report_generator/materials.json`

Defaults include material curves:

- `N48`
- `N48_Linear`

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Functional Mapping

### Tab 1 - Magnet Data

- Project
- COMSOL Version (default 6.4, persisted)
- Date (auto)
- Original TXT file browse
- Expected TXT columns:
  - x, y, z, Br, mx, my, mz, sx, sy, sz
- Automatically computes:
  - Number of magnets
  - Number of rings (group by identical x)
  - Ring table (Ring, X position, Magnets)
  - Br
  - Magnet size (sx x sy x sz)
  - Magnet length
  - Major/minor ellipse side with axis direction

### Tab 2 - Simulation Results

- Parent folder selection
- Auto-detect first-level subfolders
- Multi-study configuration through row checkboxes
- Per-study symmetry and material selection
- Material database supports:
  - New Material
  - Duplicate
  - Delete
  - Edit values
  - Add to Magnet Database
- Auto-detect and group PNG figures by naming patterns:
  - B_<Domain>_3DPlot
  - B_<Domain>_Histogram
  - B_<Domain>_CustomCoordinates
  - Magnets_3DPlot
  - Magnets_Histogram

### Tab 3 - Report Preview

- Live text preview from selected/loaded state.

### Tab 4 - Generate Report

- Generate PDF
- Export PDF
- Professional ReportLab formatting with automatic page numbering.

## Extensibility

- Add new image types by extending `SimulationService` regex grouping.
- Add new report sections in `ReportService`.
- Add new user settings in `AppSettings` and `SettingsService`.
