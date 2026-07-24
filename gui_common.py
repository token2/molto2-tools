# -*- coding: utf-8 -*-
# Shared Qt theme (palette + stylesheet) for gui.py and gui-single.py.
# Extracted to remove the duplicated styling between the two front-ends (#18).

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt

STYLESHEET = """
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: #191e32;
    background-color: #f2f4f8;
}
QGroupBox {
    border: 1px solid #c5cade;
    border-radius: 7px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
    color: #4a5478;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
}
QLineEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #b8bdd4;
    border-radius: 5px;
    padding: 5px 9px;
    color: #191e32;
}
QLineEdit:focus, QComboBox:focus {
    border: 1.5px solid #0070c8;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #b8bdd4;
    color: #191e32;
    selection-background-color: #0070c8;
    selection-color: white;
    padding: 2px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 8px;
}
QPushButton {
    background-color: #e4e7f2;
    border: 1px solid #b8bdd4;
    border-radius: 5px;
    padding: 6px 14px;
    color: #191e32;
}
QPushButton:hover   { background-color: #d2d7ec; border-color: #8890b8; }
QPushButton:pressed { background-color: #c0c7e0; }
QPushButton#btn_primary {
    background-color: #0070c8;
    border-color: #0058a0;
    color: white;
    font-weight: bold;
}
QPushButton#btn_primary:hover   { background-color: #1a82d8; }
QPushButton#btn_primary:pressed { background-color: #0058a0; }
QPushButton#btn_danger {
    background-color: #c0392b;
    border-color: #962d22;
    color: white;
    font-weight: bold;
}
QPushButton#btn_danger:hover   { background-color: #d44637; }
QPushButton#btn_danger:pressed { background-color: #962d22; }
QPushButton#btn_warning {
    background-color: #e67e22;
    border-color: #b8621a;
    color: white;
    font-weight: bold;
}
QPushButton#btn_warning:hover   { background-color: #f08c35; }
QPushButton#btn_warning:pressed { background-color: #b8621a; }
QPushButton#btn_secondary {
    background-color: #6c757d;
    border-color: #545b62;
    color: white;
}
QPushButton#btn_secondary:hover   { background-color: #7d868f; }
QPushButton#btn_secondary:pressed { background-color: #545b62; }
QCheckBox { spacing: 6px; }
QTabWidget::pane {
    border: 1px solid #c5cade;
    border-radius: 6px;
    background-color: #f2f4f8;
}
QTabBar::tab {
    background-color: #dde0ee;
    border: 1px solid #c5cade;
    border-bottom: none;
    border-radius: 5px 5px 0 0;
    padding: 6px 18px;
    margin-right: 3px;
    color: #5a6080;
}
QTabBar::tab:selected { background-color: #f2f4f8; color: #191e32; border-bottom: 1px solid #f2f4f8; }
QTabBar::tab:hover    { background-color: #cdd2e8; color: #191e32; }
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f0f2f8;
    gridline-color: #dde0ee;
    border: 1px solid #c5cade;
    border-radius: 4px;
}
QTableWidget::item { padding: 3px 6px; }
QHeaderView::section {
    background-color: #e4e7f2;
    border: none;
    border-right: 1px solid #c5cade;
    border-bottom: 1px solid #c5cade;
    padding: 5px 8px;
    color: #4a5478;
    font-weight: bold;
}
QScrollBar:vertical {
    background: #e4e7f2; width: 10px; border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #a8b0cc; border-radius: 5px; min-height: 20px;
}
QLabel#status_bar {
    border-radius: 5px;
    padding: 5px 12px;
    font-weight: bold;
    font-size: 13px;
}
QFrame#divider {
    background-color: #c5cade;
    max-height: 1px;
}
"""


def apply_theme(app):
    """Apply the Fusion style, light palette and stylesheet to a QApplication."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(242, 244, 248))
    palette.setColor(QPalette.WindowText,      QColor(25,  30,  50))
    palette.setColor(QPalette.Base,            QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase,   QColor(235, 238, 245))
    palette.setColor(QPalette.ToolTipBase,     QColor(255, 255, 220))
    palette.setColor(QPalette.ToolTipText,     QColor(25,  30,  50))
    palette.setColor(QPalette.Text,            QColor(25,  30,  50))
    palette.setColor(QPalette.Button,          QColor(220, 224, 235))
    palette.setColor(QPalette.ButtonText,      QColor(25,  30,  50))
    palette.setColor(QPalette.BrightText,      Qt.red)
    palette.setColor(QPalette.Highlight,       QColor(0,   112, 200))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
