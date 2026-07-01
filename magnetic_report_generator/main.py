from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.services.magnet_data_service import MagnetDataService
from app.services.report_service import ReportService
from app.services.settings_service import SettingsService
from app.services.simulation_service import SimulationService


def main() -> int:
    app = QApplication(sys.argv)

    settings_service = SettingsService()
    magnet_data_service = MagnetDataService()
    simulation_service = SimulationService()
    report_service = ReportService()

    window = MainWindow(
        settings_service=settings_service,
        magnet_data_service=magnet_data_service,
        simulation_service=simulation_service,
        report_service=report_service,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
