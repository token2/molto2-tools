#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Token2 Molto2 USB Config Tool — PyQt5 GUI (front-end for molto2.py)
# Copyright (c) 2023-2026 Token2 Sarl
# Released under the MIT License. See LICENSE.md for details.

import sys
import io
import secrets
import base64
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime

import molto2
from smartcard.System import readers
from PyQt5.QtWidgets import (
    QApplication, QDialog, QTableWidgetItem, QMessageBox,
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTabWidget,
    QTableWidget, QHeaderView, QSizePolicy, QFrame, QSpacerItem
)
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtCore import Qt, QTimer

# ---------------------------------------------------------------------------
# Build the GUI programmatically (no .ui file dependency)
# ---------------------------------------------------------------------------

app = QApplication(sys.argv)
app.setStyle("Fusion")

# Light palette
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
app.setStyleSheet(STYLESHEET)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

window = QDialog()
window.setWindowTitle("TOKEN2 Molto2 — Config Tool")
window.setMinimumSize(820, 720)

root_layout = QVBoxLayout(window)
root_layout.setContentsMargins(12, 12, 12, 12)
root_layout.setSpacing(8)

# ── Status bar ───────────────────────────────────────────────────────────────
status_row = QHBoxLayout()
status_label = QLabel("  ○ TOKEN2 Molto2 disconnected")
status_label.setObjectName("status_bar")
status_label.setStyleSheet(
    "background-color:#8b1a1a;color:white;border-radius:5px;padding:5px 12px;font-weight:bold;"
)
serial_label = QLabel("Serial: —")
serial_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
serial_label.setStyleSheet("color:#5a6080;font-size:12px;")
status_row.addWidget(status_label, 1)
status_row.addWidget(serial_label)
root_layout.addLayout(status_row)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = QTabWidget()
root_layout.addWidget(tabs, 1)

# ============================================================
# TAB 1 — Provisioning
# ============================================================
tab_provision = QWidget()
tabs.addTab(tab_provision, "🔑  Provisioning")
prov_layout = QVBoxLayout(tab_provision)
prov_layout.setSpacing(10)

# — Profile selector
profile_row = QHBoxLayout()
profile_row.addWidget(QLabel("Profile #:"))
cb_profile = QComboBox()
cb_profile.addItems([str(i) for i in range(100)])
cb_profile.setFixedWidth(70)
profile_row.addWidget(cb_profile)
profile_row.addSpacing(20)
profile_row.addWidget(QLabel("Title (≤12 chars):"))
le_title = QLineEdit()
le_title.setPlaceholderText("Optional profile title")
le_title.setMaxLength(12)
profile_row.addWidget(le_title, 1)
btn_set_title = QPushButton("Set Title")
profile_row.addWidget(btn_set_title)
prov_layout.addLayout(profile_row)

# — Seed group
grp_seed = QGroupBox("Seed")
seed_layout = QVBoxLayout(grp_seed)
seed_top = QHBoxLayout()
chk_hex_seed = QCheckBox("HEX format (uncheck = Base32)")
chk_hex_seed.setChecked(False)   # Base32 is default
seed_top.addWidget(chk_hex_seed)
seed_top.addStretch()
seed_layout.addLayout(seed_top)

seed_field_row = QHBoxLayout()
le_seed = QLineEdit()
le_seed.setPlaceholderText("Paste seed here (base32 or hex)")
le_seed.setFont(QFont("Courier New", 11))
btn_random_seed = QPushButton("🎲 Random")
btn_random_seed.setObjectName("btn_secondary")
btn_random_seed.setToolTip("Generate a cryptographically random 20-byte Base32 seed")
btn_random_seed.setFixedWidth(100)
seed_field_row.addWidget(le_seed)
seed_field_row.addWidget(btn_random_seed)
seed_layout.addLayout(seed_field_row)

seed_btns = QHBoxLayout()
btn_write_seed = QPushButton("Write Seed Only")
btn_write_seed.setObjectName("btn_primary")
btn_remove_seed = QPushButton("🗑  Delete Seed")
btn_remove_seed.setObjectName("btn_danger")
seed_btns.addWidget(btn_write_seed)
seed_btns.addWidget(btn_remove_seed)
seed_btns.addStretch()
seed_layout.addLayout(seed_btns)
prov_layout.addWidget(grp_seed)

# — Config group
grp_config = QGroupBox("TOTP Configuration")
cfg_outer = QVBoxLayout(grp_config)
cfg_outer.setSpacing(10)

def make_cfg_cell(label_text, widget):
    cell = QVBoxLayout()
    cell.setSpacing(4)
    lbl = QLabel(label_text)
    lbl.setStyleSheet("font-size:12px; color:#4a5478; font-weight:bold;")
    widget.setFixedHeight(32)
    cell.addWidget(lbl)
    cell.addWidget(widget)
    return cell

cb_timestep  = QComboBox(); cb_timestep.addItems(["30s", "60s"])
cb_algorithm = QComboBox(); cb_algorithm.addItems(["SHA1", "SHA256"])
cb_timeout   = QComboBox(); cb_timeout.addItems(["15s", "30s", "60s", "120s"])
cb_timeout.setCurrentIndex(1)
cb_otplen    = QComboBox(); cb_otplen.addItems(["4", "6", "8", "10"])
cb_otplen.setCurrentIndex(1)

cfg_cells_row = QHBoxLayout()
cfg_cells_row.setSpacing(16)
cfg_cells_row.addLayout(make_cfg_cell("Time step", cb_timestep))
cfg_cells_row.addLayout(make_cfg_cell("Algorithm", cb_algorithm))
cfg_cells_row.addLayout(make_cfg_cell("Display timeout", cb_timeout))
cfg_cells_row.addLayout(make_cfg_cell("OTP digits", cb_otplen))

chk_synctime = QCheckBox("Sync device time on write")
chk_synctime.setChecked(True)

cfg_outer.addLayout(cfg_cells_row)
cfg_outer.addWidget(chk_synctime)
prov_layout.addWidget(grp_config)

# — Provision buttons
prov_btns = QHBoxLayout()
chk_use_config = QCheckBox("Include config when provisioning")
chk_use_config.setChecked(True)
btn_provision   = QPushButton("⚡  Provision Profile")
btn_provision.setObjectName("btn_primary")
btn_apply_cfg   = QPushButton("Apply Config Only")
prov_btns.addWidget(chk_use_config)
prov_btns.addStretch()
prov_btns.addWidget(btn_apply_cfg)
prov_btns.addWidget(btn_provision)
prov_layout.addLayout(prov_btns)
prov_layout.addStretch()

# ============================================================
# TAB 2 — Time Sync
# ============================================================
tab_time = QWidget()
tabs.addTab(tab_time, "🕒  Time Sync")
time_layout = QVBoxLayout(tab_time)
time_layout.setSpacing(12)
time_layout.addSpacing(8)

grp_time = QGroupBox("Synchronise Device RTC")
time_inner = QVBoxLayout(grp_time)

info_lbl = QLabel(
    "Syncing writes the current PC UTC time to the device.\n"
    "Use 'All Profiles' to fix TOTP drift across every slot at once."
)
info_lbl.setStyleSheet("color:#5a6880;font-size:12px;")
time_inner.addWidget(info_lbl)
time_inner.addSpacing(8)

time_row1 = QHBoxLayout()
time_row1.addWidget(QLabel("Profile #:"))
cb_sync_profile = QComboBox()
cb_sync_profile.addItems([str(i) for i in range(100)])
cb_sync_profile.setFixedWidth(70)
time_row1.addWidget(cb_sync_profile)
time_row1.addSpacing(12)
btn_sync_one   = QPushButton("Sync This Profile")
btn_sync_one.setObjectName("btn_primary")
btn_sync_all   = QPushButton("Sync ALL Profiles")
btn_sync_all.setObjectName("btn_warning")
time_row1.addWidget(btn_sync_one)
time_row1.addWidget(btn_sync_all)
time_row1.addStretch()
time_inner.addLayout(time_row1)

time_layout.addWidget(grp_time)
time_layout.addStretch()

# ============================================================
# TAB 3 — Customer Key
# ============================================================
tab_key = QWidget()
tabs.addTab(tab_key, "🔐  Customer Key")
key_layout = QVBoxLayout(tab_key)
key_layout.setSpacing(12)
key_layout.addSpacing(8)

grp_key = QGroupBox("Change Customer Key")
key_inner = QVBoxLayout(grp_key)

warn_lbl = QLabel(
    "⚠️  Changing the customer key requires physical confirmation on the device.\n"
    "After clicking 'Set Key', press the  ▲  button on the device to confirm."
)
warn_lbl.setStyleSheet(
    "color:#7a4a00;background-color:#fff3cd;border:1px solid #e0a020;"
    "border-radius:5px;padding:8px 12px;font-size:12px;"
)
warn_lbl.setWordWrap(True)
key_inner.addWidget(warn_lbl)
key_inner.addSpacing(10)

key_format_row = QHBoxLayout()
key_format_row.addWidget(QLabel("Input format:"))
cb_key_format = QComboBox()
cb_key_format.addItems(["HEX (32 hex chars)", "ASCII (16 chars)"])
cb_key_format.setFixedWidth(200)
key_format_row.addWidget(cb_key_format)
key_format_row.addStretch()
key_inner.addLayout(key_format_row)

key_current_row = QHBoxLayout()
key_current_row.addWidget(QLabel("Current key:"))
le_current_key = QLineEdit()
le_current_key.setPlaceholderText("Current customer key (leave blank for default)")
le_current_key.setFont(QFont("Courier New", 11))
key_current_row.addWidget(le_current_key)
key_inner.addLayout(key_current_row)

key_new_row = QHBoxLayout()
key_new_row.addWidget(QLabel("New key:"))
le_new_key = QLineEdit()
le_new_key.setPlaceholderText("New customer key")
le_new_key.setFont(QFont("Courier New", 11))
key_new_row.addWidget(le_new_key)
key_inner.addLayout(key_new_row)

key_btn_row = QHBoxLayout()
key_btn_row.addStretch()
btn_set_key = QPushButton("🔑  Set New Customer Key")
btn_set_key.setObjectName("btn_warning")
key_btn_row.addWidget(btn_set_key)
key_inner.addLayout(key_btn_row)

key_layout.addWidget(grp_key)
key_layout.addStretch()

# ============================================================
# TAB 4 — Device
# ============================================================
tab_device = QWidget()
tabs.addTab(tab_device, "📟  Device")
dev_layout = QVBoxLayout(tab_device)
dev_layout.setSpacing(12)
dev_layout.addSpacing(8)

grp_lock = QGroupBox("Screen Lock / Unlock  (v2.1+)")
lock_inner = QHBoxLayout(grp_lock)
btn_lock   = QPushButton("🔒  Lock Screen")
btn_unlock = QPushButton("🔓  Unlock Screen")
lock_inner.addWidget(btn_lock)
lock_inner.addWidget(btn_unlock)
lock_inner.addStretch()
dev_layout.addWidget(grp_lock)

grp_reset = QGroupBox("Factory Reset")
reset_inner = QVBoxLayout(grp_reset)
reset_warn = QLabel(
    "⚠️  Deletes ALL profiles and resets the customer key to factory default.\n"
    "This action cannot be undone. Physical confirmation on the device is required."
)
reset_warn.setStyleSheet(
    "color:#7a1010;background-color:#fde8e8;border:1px solid #e08080;"
    "border-radius:5px;padding:8px 12px;font-size:12px;"
)
reset_warn.setWordWrap(True)
reset_inner.addWidget(reset_warn)
btn_factory_reset = QPushButton("⚠️  Factory Reset")
btn_factory_reset.setObjectName("btn_danger")
btn_factory_reset.setFixedWidth(180)
reset_inner.addWidget(btn_factory_reset)
dev_layout.addWidget(grp_reset)
dev_layout.addStretch()

# ============================================================
# Log table (bottom, shared across all tabs)
# ============================================================
divider = QFrame()
divider.setObjectName("divider")
divider.setFrameShape(QFrame.HLine)
root_layout.addWidget(divider)

log_header = QHBoxLayout()
log_lbl = QLabel("Activity Log")
log_lbl.setStyleSheet("font-weight:bold;color:#8090a8;font-size:12px;")
btn_clear_log = QPushButton("Clear Log")
btn_clear_log.setFixedWidth(90)
log_header.addWidget(log_lbl)
log_header.addStretch()
log_header.addWidget(btn_clear_log)
root_layout.addLayout(log_header)

log_table = QTableWidget(0, 4)
log_table.setHorizontalHeaderLabels(["Time", "Serial", "Status", "Detail"])
log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
log_table.verticalHeader().setVisible(False)
log_table.setAlternatingRowColors(True)
log_table.setEditTriggers(QTableWidget.NoEditTriggers)
log_table.setSelectionBehavior(QTableWidget.SelectRows)
log_table.setFixedHeight(180)
root_layout.addWidget(log_table)

window.show()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_command(command):
    """
    Run a molto2 sub-command in-process by calling molto2.main(arglist).
    Returns (success: bool, reason: str, code: int) where code is the exit
    code (0 on success).

    Running in-process (rather than spawning `python molto2.py ...`) keeps the
    customer key and TOTP seed out of the OS process table, and removes the
    dependency on molto2.py living in the current working directory.
    """
    buf = io.StringIO()
    code = 0
    # Pause connection polling so the 2s reader poll cannot open a competing
    # PC/SC connection while this operation holds the device (#12).
    timer.stop()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            molto2.main(command)
    except SystemExit as exc:
        code = 0 if exc.code is None else (exc.code if isinstance(exc.code, int) else 1)
    except Exception as exc:  # noqa: BLE001 - surface any unexpected failure to the log
        return False, str(exc), 1
    finally:
        timer.start(2000)

    lines = buf.getvalue().strip().splitlines()
    if code == 0:
        detail = next((l for l in reversed(lines) if l.startswith("[+")), "")
        return True, detail, 0
    reason = next(
        (l for l in reversed(lines) if l.startswith(("[!", "[x", "[-"))),
        "Unknown error — check device connection and key."
    )
    return False, reason, code


def write_log(status: str, detail: str = "", is_error: bool = False):
    serial = serial_label.text().replace("Serial: ", "")
    now = datetime.now().strftime("%H:%M:%S")
    row = log_table.rowCount()
    log_table.insertRow(row)

    items = [
        QTableWidgetItem(now),
        QTableWidgetItem(serial),
        QTableWidgetItem(status),
        QTableWidgetItem(detail),
    ]
    if is_error:
        red = QColor(180, 30, 30)
        for it in items: it.setForeground(red)
    else:
        items[2].setForeground(QColor(20, 140, 60))

    for col, it in enumerate(items):
        log_table.setItem(row, col, it)
    log_table.scrollToBottom()


def dispatch(command, success_msg: str, error_prefix: str = ""):
    ok, detail, code = run_command(command)
    if ok:
        write_log(success_msg, detail, is_error=False)
    else:
        if code == molto2.EXIT_SEED_EXISTS:
            profile = cb_profile.currentText()
            reply = QMessageBox.warning(
                window,
                "Seed Already Exists",
                f"⚠️  Profile #{profile} already has a seed configured.\n\n"
                "You must remove the existing seed before writing a new one "
                "or applying config.\n\nWould you like to delete it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                remove_seed()
            else:
                write_log(error_prefix or "Operation failed",
                          "Seed not removed — cancelled.", is_error=True)
        else:
            write_log(error_prefix or "Operation failed", detail, is_error=True)
    return ok


def confirm(title: str, message: str) -> bool:
    reply = QMessageBox.question(
        window, title, message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return reply == QMessageBox.Yes


def get_seed_args():
    flag = "--seed" if chk_hex_seed.isChecked() else "--seedbase32"
    return [flag, le_seed.text()]


def get_config_args():
    timestep = "1" if cb_timestep.currentText() == "30s" else "2"
    algorithm = "1" if cb_algorithm.currentText() == "SHA1" else "2"
    display_timeout = {"15s": "0", "30s": "1", "60s": "2", "120s": "3"}.get(
        cb_timeout.currentText(), "1"
    )
    otp_length = cb_otplen.currentText()
    args = [
        "--display_timeout", display_timeout,
        "--algorithm", algorithm,
        "--timestep", timestep,
        "--otpdigits", otp_length,
    ]
    if chk_synctime.isChecked():
        args.append("--synctime")
    return args


def get_key_args():
    """Return the --key or --keyascii args for the current key field, if filled."""
    val = le_current_key.text().strip()
    if not val:
        return []
    if cb_key_format.currentIndex() == 0:
        return ["--key", val]
    return ["--keyascii", val]


# ---------------------------------------------------------------------------
# Device connection (timer)
# ---------------------------------------------------------------------------

def connection():
    reader = next(
        (r for r in readers() if "TOKEN2".lower() in r.name.lower()), None
    )
    try:
        if reader is None:
            raise RuntimeError("No TOKEN2 reader found")
        conn = reader.createConnection()
        conn.connect()
        SELECT = [0x80, 0x41, 0x00, 0x00, 0x00]
        data, sw1, sw2 = conn.transmit(SELECT)
        info = bytes(data)
        serial_len = int(info[3])
        serial = info[4:4 + serial_len].decode("utf-8")

        status_label.setText("  ● TOKEN2 Molto2 connected")
        status_label.setStyleSheet(
            "background-color:#1e7e3a;color:white;border-radius:5px;"
            "padding:5px 12px;font-weight:bold;"
        )
        serial_label.setText(f"Serial: {serial}")
        tabs.setEnabled(True)
    except Exception:
        status_label.setText("  ○ TOKEN2 Molto2 disconnected")
        status_label.setStyleSheet(
            "background-color:#8b1a1a;color:white;border-radius:5px;"
            "padding:5px 12px;font-weight:bold;"
        )
        serial_label.setText("Serial: —")
        tabs.setEnabled(False)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def set_title():
    profile = cb_profile.currentText()
    title = le_title.text().strip()
    if not title:
        write_log("Set title skipped", "Title field is empty.", is_error=True)
        return
    dispatch(
        ["--profile", profile, "--title", title]
        + get_key_args(),
        success_msg="Title set",
        error_prefix="Set title failed",
    )


def factory_reset():
    if not confirm(
        "Factory Reset",
        "⚠️  This will DELETE all profiles and reset the customer key.\n\n"
        "Are you sure you want to continue?",
    ):
        write_log("Factory reset", "Cancelled by user.")
        return
    dispatch(
        ["--factoryreset"] + get_key_args(),
        success_msg="Factory reset initiated — confirm on device",
        error_prefix="Factory reset failed",
    )


def write_seed_only():
    seed = le_seed.text().strip()
    profile = cb_profile.currentText()
    if not seed:
        write_log("Write seed skipped", "Seed field is empty.", is_error=True)
        return
    dispatch(
        ["--profile", profile]
        + get_seed_args()
        + get_key_args(),
        success_msg=f"Seed written to profile #{profile}",
        error_prefix=f"Seed write failed for profile #{profile}",
    )


def remove_seed():
    profile = cb_profile.currentText()
    if not confirm(
        "Delete Seed",
        f"⚠️  This will permanently delete the seed on profile #{profile}.\n\n"
        "Other profile settings will be kept.\n\nAre you sure?",
    ):
        write_log(f"Delete seed #{profile}", "Cancelled by user.")
        return
    dispatch(
        ["--profile", profile, "--deleteseed"]
        + get_key_args(),
        success_msg=f"Seed deleted from profile #{profile}",
        error_prefix=f"Seed delete failed for profile #{profile}",
    )


def apply_only_config():
    profile = cb_profile.currentText()
    dispatch(
        ["--config", "--profile", profile]
        + get_config_args()
        + get_key_args(),
        success_msg=f"Config applied to profile #{profile}",
        error_prefix=f"Config failed for profile #{profile}",
    )


def provision_without_config():
    seed = le_seed.text().strip()
    profile = cb_profile.currentText()
    title = le_title.text().strip()
    if not seed:
        write_log("Provision skipped", "Seed field is empty.", is_error=True)
        return
    cmd = (
        ["--profile", profile]
        + get_seed_args()
        + (["--title", title] if title else [])
        + get_key_args()
    )
    dispatch(cmd,
             success_msg=f"Profile #{profile} provisioned (seed + title)",
             error_prefix=f"Provision failed for profile #{profile}")


def provision_with_config():
    seed = le_seed.text().strip()
    profile = cb_profile.currentText()
    title = le_title.text().strip()
    if not seed:
        write_log("Provision skipped", "Seed field is empty.", is_error=True)
        return

    # Step 1: apply config first (requires empty profile)
    cmd_cfg = (
        ["--config", "--profile", profile]
        + get_config_args()
        + get_key_args()
    )
    ok = dispatch(cmd_cfg,
                  success_msg=f"Profile #{profile} — config applied",
                  error_prefix=f"Provision failed (config) for profile #{profile}")
    if not ok:
        return

    # Step 2: write seed (+ optional title)
    cmd_seed = (
        ["--profile", profile]
        + get_seed_args()
        + (["--title", title] if title else [])
        + get_key_args()
    )
    dispatch(cmd_seed,
             success_msg=f"Profile #{profile} fully provisioned (config + seed + title)",
             error_prefix=f"Provision failed (seed) for profile #{profile}")


def provision():
    if chk_use_config.isChecked():
        provision_with_config()
    else:
        provision_without_config()


def lock_device():
    dispatch(
        ["--lock"] + get_key_args(),
        success_msg="Device screen locked",
        error_prefix="Lock failed",
    )


def unlock_device():
    dispatch(
        ["--unlock"] + get_key_args(),
        success_msg="Device screen unlocked",
        error_prefix="Unlock failed",
    )


def sync_time_one():
    profile = cb_sync_profile.currentText()
    dispatch(
        ["--profile", profile, "--synctime"]
        + get_key_args(),
        success_msg=f"Time synced on profile #{profile}",
        error_prefix=f"Time sync failed for profile #{profile}",
    )


def sync_time_all():
    if not confirm(
        "Sync All Profiles",
        "This will write the current UTC time to every profile slot (0–99).\n\n"
        "This may take a moment. Continue?",
    ):
        write_log("Sync all profiles", "Cancelled by user.")
        return
    dispatch(
        ["--synctimeall"] + get_key_args(),
        success_msg="Time synced on ALL profiles",
        error_prefix="Time sync (all profiles) failed",
    )


def set_customer_key():
    new_key = le_new_key.text().strip()
    if not new_key:
        write_log("Set key skipped", "New key field is empty.", is_error=True)
        return

    use_hex = cb_key_format.currentIndex() == 0
    if use_hex and len(new_key) != 32:
        write_log("Set key skipped",
                  "HEX key must be exactly 32 hex characters (128-bit).",
                  is_error=True)
        return
    if not use_hex and len(new_key) != 16:
        write_log("Set key skipped",
                  "ASCII key must be exactly 16 characters.",
                  is_error=True)
        return

    if not confirm(
        "Change Customer Key",
        "⚠️  You are about to change the device customer key.\n\n"
        "After clicking Yes, press the  ▲  button on the device to confirm.\n\n"
        "If you lose the new key, data may become inaccessible. Continue?",
    ):
        write_log("Set customer key", "Cancelled by user.")
        return

    key_flag = "--setkey" if use_hex else "--setkeyascii"
    dispatch(
        [key_flag, new_key] + get_key_args(),
        success_msg="Customer key change sent — confirm on device (▲)",
        error_prefix="Customer key change failed",
    )


def generate_random_seed():
    """Fill le_seed with a cryptographically random 20-byte Base32 seed."""
    raw = secrets.token_bytes(20)
    b32 = base64.b32encode(raw).decode("ascii")
    le_seed.setText(b32)
    chk_hex_seed.setChecked(False)   # ensure Base32 mode is active
    write_log("Random seed generated", "Paste into your authenticator app before provisioning.")


def clear_log():
    log_table.setRowCount(0)


# ---------------------------------------------------------------------------
# Wire up signals
# ---------------------------------------------------------------------------

btn_set_title.clicked.connect(set_title)
btn_random_seed.clicked.connect(generate_random_seed)
btn_write_seed.clicked.connect(write_seed_only)
btn_remove_seed.clicked.connect(remove_seed)
btn_provision.clicked.connect(provision)
btn_apply_cfg.clicked.connect(apply_only_config)

btn_sync_one.clicked.connect(sync_time_one)
btn_sync_all.clicked.connect(sync_time_all)

btn_set_key.clicked.connect(set_customer_key)

btn_lock.clicked.connect(lock_device)
btn_unlock.clicked.connect(unlock_device)
btn_factory_reset.clicked.connect(factory_reset)

btn_clear_log.clicked.connect(clear_log)

timer = QTimer()
timer.timeout.connect(connection)
timer.start(2000)

sys.exit(app.exec())