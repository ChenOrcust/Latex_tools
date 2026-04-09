from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from .app import FormulaToolWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("LaTeX Formula Tool")
    app.setOrganizationName("LatexTools")

    window = FormulaToolWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

