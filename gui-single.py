#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# TOKEN2 Molto2 GUI — self-contained (molto2 logic embedded)
# Copyright (c) 2023-2026 Token2 Sarl
# Released under the MIT License. See LICENSE.md for details.

import sys
import io
import secrets
import base64
import hashlib
from binascii import unhexlify, hexlify
from datetime import datetime
from time import time as timestamp
from contextlib import redirect_stdout, redirect_stderr

from smartcard.System import readers as sc_readers
from sm4 import SM4Key

from PyQt5.QtWidgets import (
    QApplication, QDialog, QTableWidgetItem, QMessageBox,
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTabWidget,
    QTableWidget, QHeaderView, QFrame,
)
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtCore import Qt, QTimer


# ===========================================================================
# Embedded molto2 logic
# ===========================================================================

DEFAULT_CUSTOMER_KEY = "544F4B454E324D4F4C544F312D4B4559"


def _get_connection():
    reader = next(
        (r for r in sc_readers() if "TOKEN2".lower() in r.name.lower()), None
    )
    if reader is None:
        raise RuntimeError("No TOKEN2 reader found")
    conn = reader.createConnection()
    conn.connect()
    return conn


def _sw_ok(sw1):
    return sw1 == 144


def _die(msg):
    print("[!] " + msg)
    raise SystemExit(1)


def _calc_mac(key, message: bytes) -> bytes:
    msg = message
    if len(msg) % 16 != 0:
        msg += b'\x80' + b'\x00' * (15 - len(msg) % 16)
    sm4 = SM4Key(key)
    mac = sm4.encrypt(msg, initial=b'\0' * 16)
    return mac[-16:-16 + 4]


def _profile_has_seed(conn, profile_num):
    apdu = [0x80, 0x41, 0x00, profile_num, 0x01, 0x70]
    resp, sw1, sw2 = conn.transmit(apdu)
    if not _sw_ok(sw1):
        return False
    try:
        rb = bytes(resp)
        if rb[0] != 0x95:
            return False
        inner = rb[2:]
        idx = 0
        while idx < len(inner):
            tag = inner[idx]
            length = inner[idx + 1]
            value = inner[idx + 2: idx + 2 + length]
            if tag == 0x70:
                return value[-1] == 0x01
            idx += 2 + length
    except Exception:
        pass
    return False


def _resolve_key(key_hex=None, key_ascii=None):
    if key_hex is None and key_ascii is None:
        print("[!] Note: No customer key provided, using default.")
        return unhexlify(DEFAULT_CUSTOMER_KEY)
    if key_hex is not None:
        return unhexlify(key_hex)
    return unhexlify(key_ascii.encode("utf-8").hex())


def molto2_run(args: dict):
    """
    Execute molto2 logic given a dict of arguments.
    Keys mirror molto2.py CLI flags (without --):
      profile, title, seed, seedbase32, key, keyascii,
      setkey, setkeyascii, config, synctime, synctimeall,
      display_timeout, algorithm, timestep, otpdigits,
      factoryreset, lock, unlock, deleteseed, timevalue
    Raises SystemExit(1) on error, returns normally on success.
    """
    conn = _get_connection()

    # ── Read serial ────────────────────────────────────────────────────────
    data, sw1, _sw2 = conn.transmit([0x80, 0x41, 0x00, 0x00, 0x00])
    info = bytes(data)
    serial_len = int(info[3])
    serial = info[4:4 + serial_len].decode("utf-8")
    print(f"[+] device serial: {serial}")

    # ── Factory reset (no authentication required) ─────────────────────────
    # Must run before the auth handshake: a forgotten/incorrect customer key
    # is exactly when a factory reset is needed for recovery.
    if args.get("factoryreset"):
        _data, sw1, _sw2 = conn.transmit([0x80, 0x56, 0x00, 0x00, 0x00])
        if not _sw_ok(sw1):
            _die(f"[!] Factory reset request failed (SW={hex(sw1)}{hex(_sw2)})")
        print("[+] Factory reset request sent — PLEASE CONFIRM ON THE DEVICE BY PRESSING ▲")
        return

    # ── Resolve customer key ───────────────────────────────────────────────
    customer_key = _resolve_key(args.get("key"), args.get("keyascii"))
    key_sha1 = hashlib.sha1(customer_key).digest()[:16]

    # ── Profile ────────────────────────────────────────────────────────────
    profile_arg = args.get("profile")
    if profile_arg is not None:
        profile_number = int(profile_arg)
        prof = hex(profile_number)[2:].zfill(2)
    else:
        profile_number = 0
        prof = "00"

    # ── Authenticate ───────────────────────────────────────────────────────
    data, sw1, _sw2 = conn.transmit([0x80, 0x4b, 0x08, 0x00, 0x00])
    challenge = bytes(data) + b'\x00' * 8
    sm4 = SM4Key(key_sha1)
    response_raw = sm4.encrypt(challenge)
    apdu = [0x80, 0xCE, 0x00, 0x00, 0x10]
    apdu.extend(response_raw)
    _data, sw1, sw2 = conn.transmit(apdu)
    if sw1 == 99:
        _die(f"[-] Authentication failure, attempts left: {sw2}")
    if not _sw_ok(sw1):
        _die("[-] Authentication failed")
    print("[+] Authentication successful")

    # ── Delete seed ────────────────────────────────────────────────────────
    if args.get("deleteseed"):
        if profile_arg is None:
            _die("[x] No profile number provided for deleteseed")
        apdu = [0x80, 0xE6, 0x00, profile_number, 0x00]
        _data, sw1, _sw2 = conn.transmit(apdu)
        if _sw_ok(sw1):
            print(f"[+] Seed deleted successfully for profile [#{profile_arg}]")
        else:
            _die(f"[!] Seed delete failed for profile [#{profile_arg}]")

    # ── Resolve seed ───────────────────────────────────────────────────────
    seed_hex = args.get("seed")
    seed_b32 = args.get("seedbase32")
    if seed_hex is not None and seed_b32 is not None:
        _die("[!] Provide seed in only one format (hex or base32)")
    if seed_b32 is not None:
        normalized = seed_b32 + '=' * (-len(seed_b32) % 8)
        seed_hex = base64.b16encode(base64.b32decode(normalized)).decode("utf-8")

    # ── Write seed ─────────────────────────────────────────────────────────
    if seed_hex is not None:
        if profile_arg is None:
            _die("[x] No profile number provided")
        if len(seed_hex) % 2 != 0:
            _die("[!] Seed hex-string length invalid")
        if len(seed_hex) > 63 * 2:
            _die("[!] Seed too long")

        seed_bytes = unhexlify(seed_hex)
        is_deleting = seed_bytes == b'\x00' * len(seed_bytes)

        if not is_deleting:
            if _profile_has_seed(conn, profile_number):
                _die(f"[x] Profile #{profile_arg} already has a seed. Delete it first.")
            print(f"[+] Profile [#{profile_arg}] is empty. Writing seed.")

        if seed_bytes == b'\x00' * 20:
            seed_padded = seed_bytes + b'\x00' * (16 - len(seed_bytes) % 16)
        else:
            seed_padded = seed_bytes + b'\x80' + b'\x00' * (15 - len(seed_bytes) % 16)

        sm4 = SM4Key(key_sha1)
        enc_seed = sm4.encrypt(seed_padded)
        add_len = hex(len(enc_seed))[2:].zfill(2)
        mac_packet = unhexlify("80C501" + prof + add_len) + enc_seed
        mac = _calc_mac(key_sha1, mac_packet)
        data_out = enc_seed + mac
        apdu = [0x84, 0xC5, 0x01, profile_number, len(data_out)]
        apdu.extend(data_out)
        _data, sw1, _sw2 = conn.transmit(apdu)
        if _sw_ok(sw1):
            print(f"[+] Seed was set successfully")
        else:
            _die(f"[!] Seed write failed")

    # ── Set title ──────────────────────────────────────────────────────────
    title_arg = args.get("title")
    if title_arg is not None:
        if len(title_arg) > 12:
            _die("[!] Profile title cannot be longer than 12 symbols")
        title_b = title_arg.encode("utf-8")
        if len(title_b) % 16 != 0:
            title_b += b'\x80' + b'\x00' * (15 - len(title_b) % 16)
        sm4 = SM4Key(key_sha1)
        enc_title = sm4.encrypt(title_b)
        mac_packet = unhexlify("80D500" + prof + "10") + enc_title
        mac = _calc_mac(key_sha1, mac_packet)
        data_out = enc_title + mac
        apdu = [0x84, 0xD5, 0x00, profile_number, 0x14]
        apdu.extend(data_out)
        _data, sw1, _sw2 = conn.transmit(apdu)
        if _sw_ok(sw1):
            print(f"[+] Title was set successfully")

    # ── Apply config ───────────────────────────────────────────────────────
    if args.get("config"):
        time_val = int(args["timevalue"]) if args.get("timevalue") else int(timestamp())

        display_timeout = int(args.get("display_timeout", 99))
        if not (0 <= display_timeout <= 3):
            _die("[!] Incorrect display_timeout (0-3)")

        hmac_method = int(args.get("algorithm", 99))
        if not (1 <= hmac_method <= 2):
            _die("[!] Incorrect algorithm (1=SHA1, 2=SHA256)")

        time_step = int(args.get("timestep", 99))
        if not (1 <= time_step <= 2):
            _die("[!] Incorrect timestep (1=30s, 2=60s)")

        otp_digits = str(args.get("otpdigits", "6"))
        otp_hex = {"4": "04", "6": "06", "8": "08", "10": "0A"}.get(otp_digits, "06")

        time_hex  = hex(time_val)[2:].zfill(8)
        dt_hex    = "0" + str(display_timeout)
        hmac_hex  = "0" + str(hmac_method)
        tstep_hex = "1E" if time_step == 1 else "3C"

        cfg  = "8114"
        cfg += "1F01" + dt_hex
        cfg += "0F04" + time_hex
        cfg += "8609"
        cfg += "0A01" + hmac_hex
        cfg += "0B01" + otp_hex
        cfg += "0D01" + tstep_hex

        cfg_bytes = unhexlify(cfg)
        d_len = hex(len(cfg_bytes))[2:].zfill(2)
        mac_packet = unhexlify("80D401" + prof + d_len) + cfg_bytes
        mac = _calc_mac(key_sha1, mac_packet)
        data_out = cfg_bytes + mac
        apdu = [0x84, 0xD4, 0x01, profile_number, len(data_out)]
        apdu.extend(data_out)
        _data, sw1, _sw2 = conn.transmit(apdu)
        if _sw_ok(sw1):
            print(f"[+] Config was set successfully for profile [#{profile_arg}]")
        else:
            _die(f"[!] Config failed for profile [#{profile_arg}]")

    # ── Sync time (included in config or standalone) ───────────────────────
    if args.get("synctime") or args.get("synctimeall"):
        sync_profiles = range(100) if args.get("synctimeall") else [profile_number]
        for pnum in sync_profiles:
            p = hex(int(pnum))[2:].zfill(2)
            t = hex(int(timestamp()))[2:].zfill(8)
            td_bytes = unhexlify("8106" + "0F04" + t)
            d_len = hex(len(td_bytes))[2:].zfill(2)
            mac_packet = unhexlify("80D401" + p + d_len) + td_bytes
            mac = _calc_mac(key_sha1, mac_packet)
            data_out = td_bytes + mac
            apdu = [0x84, 0xD4, 0x01, int(pnum), len(data_out)]
            apdu.extend(data_out)
            _data, sw1, _sw2 = conn.transmit(apdu)
            if _sw_ok(sw1):
                print(f"[+] Time was set successfully for profile [#{pnum}]")
            else:
                print(f"[!] Time sync failed for profile [#{pnum}]")

    # ── Set customer key ───────────────────────────────────────────────────
    hexkey = ""
    if args.get("setkey"):
        hexkey = args["setkey"].upper()
    elif args.get("setkeyascii"):
        hexkey = args["setkeyascii"].encode("utf-8").hex().upper()

    if hexkey:
        newkey_sha1 = hashlib.sha1(unhexlify(hexkey)).digest()[:16]
        enc_data = unhexlify("00") + newkey_sha1 + unhexlify("800000000000000000000000000000")
        sm4 = SM4Key(key_sha1)
        sm4enc = sm4.encrypt(enc_data)
        mac_packet = unhexlify("80d7000020") + sm4enc
        mac = _calc_mac(key_sha1, mac_packet)
        data_out = sm4enc + mac
        apdu = [0x84, 0xD7, 0x00, 0x00, 0x24]
        apdu.extend(data_out)
        _data, sw1, _sw2 = conn.transmit(apdu)
        if _sw_ok(sw1):
            print(f"[+] New customer key sent — confirm on device (▲)")

    # ── Lock / Unlock ──────────────────────────────────────────────────────
    if args.get("lock"):
        _data, sw1, _sw2 = conn.transmit([0x80, 0xD8, 0x0C, 0x02, 0x00])
        if _sw_ok(sw1):
            print(f"[+] Device screen locked")

    if args.get("unlock"):
        _data, sw1, _sw2 = conn.transmit([0x80, 0xD8, 0x0C, 0x02, 0x01, 0x01])
        if _sw_ok(sw1):
            print(f"[+] Device screen unlocked")


def run_device_command(args: dict):
    """Call molto2_run, capture output. Returns (success, detail_str)."""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            molto2_run(args)
        lines = buf_out.getvalue().splitlines()
        detail = next((l for l in reversed(lines) if l.startswith("[+")), "")
        return True, detail
    except SystemExit:
        lines = (buf_out.getvalue() + buf_err.getvalue()).splitlines()
        reason = next(
            (l for l in reversed(lines) if l.startswith(("[!", "[x", "[-"))),
            "Unknown error — check device connection and key."
        )
        return False, reason
    except Exception as e:
        return False, str(e)


# ===========================================================================
# GUI
# ===========================================================================

from gui_common import apply_theme

app = QApplication(sys.argv)
apply_theme(app)

# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

window = QDialog()
window.setWindowTitle("TOKEN2 Molto2 — Config Tool")
window.setMinimumSize(820, 720)

root_layout = QVBoxLayout(window)
root_layout.setContentsMargins(12, 12, 12, 12)
root_layout.setSpacing(8)

# ── Status bar ────────────────────────────────────────────────────────────────
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

tabs = QTabWidget()
root_layout.addWidget(tabs, 1)

# ============================================================
# TAB 1 — Provisioning
# ============================================================
tab_provision = QWidget()
tabs.addTab(tab_provision, "🔑  Provisioning")
prov_layout = QVBoxLayout(tab_provision)
prov_layout.setSpacing(10)

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

grp_seed = QGroupBox("Seed")
seed_layout = QVBoxLayout(grp_seed)
seed_top = QHBoxLayout()
chk_hex_seed = QCheckBox("HEX format (uncheck = Base32)")
chk_hex_seed.setChecked(False)
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

# — TOTP config (side-by-side)
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

prov_btns = QHBoxLayout()
chk_use_config = QCheckBox("Include config when provisioning")
chk_use_config.setChecked(True)
btn_provision = QPushButton("⚡  Provision Profile")
btn_provision.setObjectName("btn_primary")
btn_apply_cfg = QPushButton("Apply Config Only")
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
btn_sync_one = QPushButton("Sync This Profile")
btn_sync_one.setObjectName("btn_primary")
btn_sync_all = QPushButton("Sync ALL Profiles")
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
# Log table
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
# GUI helpers
# ---------------------------------------------------------------------------

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
        for it in items:
            it.setForeground(QColor(180, 30, 30))
    else:
        items[2].setForeground(QColor(20, 140, 60))
    for col, it in enumerate(items):
        log_table.setItem(row, col, it)
    log_table.scrollToBottom()


def dispatch(args: dict, success_msg: str, error_prefix: str = ""):
    ok, detail = run_device_command(args)
    if ok:
        write_log(success_msg, detail, is_error=False)
    else:
        if "already has a seed" in detail:
            profile = cb_profile.currentText()
            reply = QMessageBox.warning(
                window, "Seed Already Exists",
                f"⚠️  Profile #{profile} already has a seed.\n\n"
                "Remove it before writing a new one or applying config.\n\n"
                "Would you like to delete it now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
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
    return QMessageBox.question(
        window, title, message,
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
    ) == QMessageBox.Yes


def get_key_args() -> dict:
    val = le_current_key.text().strip()
    if not val:
        return {}
    return {"key": val} if cb_key_format.currentIndex() == 0 else {"keyascii": val}


def get_seed_args() -> dict:
    if chk_hex_seed.isChecked():
        return {"seed": le_seed.text()}
    return {"seedbase32": le_seed.text()}


def get_config_args() -> dict:
    d = {
        "config": True,
        "display_timeout": {"15s": "0", "30s": "1", "60s": "2", "120s": "3"}.get(
            cb_timeout.currentText(), "1"),
        "algorithm": "1" if cb_algorithm.currentText() == "SHA1" else "2",
        "timestep":  "1" if cb_timestep.currentText() == "30s" else "2",
        "otpdigits": cb_otplen.currentText(),
    }
    if chk_synctime.isChecked():
        d["synctime"] = True
    return d


# ---------------------------------------------------------------------------
# Device connection (timer)
# ---------------------------------------------------------------------------

def connection():
    try:
        reader = next(
            (r for r in sc_readers() if "TOKEN2".lower() in r.name.lower()), None
        )
        if reader is None:
            raise RuntimeError("not found")
        conn = reader.createConnection()
        conn.connect()
        data, sw1, sw2 = conn.transmit([0x80, 0x41, 0x00, 0x00, 0x00])
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
    title = le_title.text().strip()
    if not title:
        write_log("Set title skipped", "Title field is empty.", is_error=True)
        return
    dispatch(
        {"profile": cb_profile.currentText(), "title": title, **get_key_args()},
        success_msg="Title set", error_prefix="Set title failed",
    )


def factory_reset():
    if not confirm("Factory Reset",
                   "⚠️  This will DELETE all profiles and reset the customer key.\n\nAre you sure?"):
        write_log("Factory reset", "Cancelled by user.")
        return
    dispatch({"factoryreset": True, **get_key_args()},
             success_msg="Factory reset initiated — confirm on device",
             error_prefix="Factory reset failed")


def write_seed_only():
    if not le_seed.text().strip():
        write_log("Write seed skipped", "Seed field is empty.", is_error=True)
        return
    profile = cb_profile.currentText()
    dispatch(
        {"profile": profile, **get_seed_args(), **get_key_args()},
        success_msg=f"Seed written to profile #{profile}",
        error_prefix=f"Seed write failed for profile #{profile}",
    )


def remove_seed():
    profile = cb_profile.currentText()
    if not confirm("Delete Seed",
                   f"⚠️  Permanently delete the seed on profile #{profile}?\n\nOther settings will be kept."):
        write_log(f"Delete seed #{profile}", "Cancelled by user.")
        return
    dispatch(
        {"profile": profile, "deleteseed": True, **get_key_args()},
        success_msg=f"Seed deleted from profile #{profile}",
        error_prefix=f"Seed delete failed for profile #{profile}",
    )


def apply_only_config():
    profile = cb_profile.currentText()
    dispatch(
        {"profile": profile, **get_config_args(), **get_key_args()},
        success_msg=f"Config applied to profile #{profile}",
        error_prefix=f"Config failed for profile #{profile}",
    )


def provision_without_config():
    if not le_seed.text().strip():
        write_log("Provision skipped", "Seed field is empty.", is_error=True)
        return
    profile = cb_profile.currentText()
    args = {"profile": profile, **get_seed_args(), **get_key_args()}
    if le_title.text().strip():
        args["title"] = le_title.text().strip()
    dispatch(args,
             success_msg=f"Profile #{profile} provisioned (seed + title)",
             error_prefix=f"Provision failed for profile #{profile}")


def provision_with_config():
    if not le_seed.text().strip():
        write_log("Provision skipped", "Seed field is empty.", is_error=True)
        return
    profile = cb_profile.currentText()

    # Step 1: config first (profile must be empty)
    ok = dispatch(
        {"profile": profile, **get_config_args(), **get_key_args()},
        success_msg=f"Profile #{profile} — config applied",
        error_prefix=f"Provision failed (config) for profile #{profile}",
    )
    if not ok:
        return

    # Step 2: seed + optional title
    seed_args = {"profile": profile, **get_seed_args(), **get_key_args()}
    if le_title.text().strip():
        seed_args["title"] = le_title.text().strip()
    dispatch(seed_args,
             success_msg=f"Profile #{profile} fully provisioned (config + seed + title)",
             error_prefix=f"Provision failed (seed) for profile #{profile}")


def provision():
    if chk_use_config.isChecked():
        provision_with_config()
    else:
        provision_without_config()


def lock_device():
    dispatch({"lock": True, **get_key_args()},
             success_msg="Device screen locked", error_prefix="Lock failed")


def unlock_device():
    dispatch({"unlock": True, **get_key_args()},
             success_msg="Device screen unlocked", error_prefix="Unlock failed")


def sync_time_one():
    profile = cb_sync_profile.currentText()
    dispatch(
        {"profile": profile, "synctime": True, **get_key_args()},
        success_msg=f"Time synced on profile #{profile}",
        error_prefix=f"Time sync failed for profile #{profile}",
    )


def sync_time_all():
    if not confirm("Sync All Profiles",
                   "Write current UTC time to every profile slot (0–99).\n\nThis may take a moment. Continue?"):
        write_log("Sync all profiles", "Cancelled by user.")
        return
    dispatch({"synctimeall": True, **get_key_args()},
             success_msg="Time synced on ALL profiles",
             error_prefix="Time sync (all profiles) failed")


def set_customer_key():
    new_key = le_new_key.text().strip()
    if not new_key:
        write_log("Set key skipped", "New key field is empty.", is_error=True)
        return
    use_hex = cb_key_format.currentIndex() == 0
    if use_hex and len(new_key) != 32:
        write_log("Set key skipped", "HEX key must be exactly 32 hex characters.", is_error=True)
        return
    if not use_hex and len(new_key) != 16:
        write_log("Set key skipped", "ASCII key must be exactly 16 characters.", is_error=True)
        return
    if not confirm("Change Customer Key",
                   "⚠️  You are about to change the device customer key.\n\n"
                   "Press ▲ on the device after clicking Yes.\n\n"
                   "If you lose the new key, data may become inaccessible. Continue?"):
        write_log("Set customer key", "Cancelled by user.")
        return
    key_arg = {"setkey": new_key} if use_hex else {"setkeyascii": new_key}
    dispatch({**key_arg, **get_key_args()},
             success_msg="Customer key change sent — confirm on device (▲)",
             error_prefix="Customer key change failed")


def generate_random_seed():
    raw = secrets.token_bytes(20)
    b32 = base64.b32encode(raw).decode("ascii")
    le_seed.setText(b32)
    chk_hex_seed.setChecked(False)
    write_log("Random seed generated", "Copy into your authenticator app before provisioning.")


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