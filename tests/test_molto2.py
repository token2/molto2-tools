# -*- coding: utf-8 -*-
# Unit tests for the pure logic and per-operation APDU construction in
# molto2.py. These require only `sm4` (pure Python) — no device, no pyscard.
#
#   pip install sm4 pytest
#   pytest

import io
import hashlib
from argparse import Namespace
from binascii import unhexlify
from contextlib import redirect_stdout

import pytest
from sm4 import SM4Key

import molto2 as m

KEY = m.derive_session_key(unhexlify(m.DEFAULT_CUSTOMER_KEY))


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_import_is_side_effect_free_without_pyscard():
    # Importing molto2 must not pull in pyscard (smartcard is imported lazily).
    import sys
    assert "smartcard" not in sys.modules


def test_derive_session_key_matches_protocol_vector():
    # docs/MOLTO2-PROTOCOL.md section 2.1
    assert KEY.hex() == "099250fdb017f442da429ecbbee17f79"


def test_calc_mac_is_four_bytes_and_pinned():
    mac = m.calc_mac(KEY, b"hello world test!!")
    assert len(mac) == 4
    assert mac.hex() == "2cf7c205"


def test_calc_mac_no_padding_when_block_aligned():
    # A 16-byte (block-aligned) message must not be padded before MAC-ing.
    msg = bytes(range(16))
    assert m.calc_mac(KEY, msg) == m.calc_mac(KEY, msg)  # deterministic


def test_base32_to_hex():
    assert m.base32_to_hex("JBSWY3DPEHPK3PXP") == "48656C6C6F21DEADBEEF"


# ---- input validation (#10) ----

@pytest.mark.parametrize("value,expected", [("0", 0), ("50", 50), ("99", 99)])
def test_validate_profile_number_accepts_valid(value, expected):
    assert m.validate_profile_number(value) == expected


@pytest.mark.parametrize("value", ["100", "-1", "abc", None, "3.5"])
def test_validate_profile_number_rejects_invalid(value):
    with pytest.raises(SystemExit) as exc:
        with redirect_stdout(io.StringIO()):
            m.validate_profile_number(value)
    assert exc.value.code != 0


def test_resolve_customer_key_default_is_16_bytes():
    with redirect_stdout(io.StringIO()):
        key = m.resolve_customer_key(None, None)
    assert key == unhexlify(m.DEFAULT_CUSTOMER_KEY) and len(key) == 16


def test_resolve_customer_key_hex_and_ascii():
    assert m.resolve_customer_key("00" * 16, None) == b"\x00" * 16
    assert m.resolve_customer_key(None, "TOKEN2MOLTO1-KEY") == b"TOKEN2MOLTO1-KEY"


def test_resolve_customer_key_ascii_wins_when_both_supplied():
    assert m.resolve_customer_key("00" * 16, "TOKEN2MOLTO1-KEY") == b"TOKEN2MOLTO1-KEY"


@pytest.mark.parametrize("key_hex", ["xyz", "00" * 15, "0" * 31])
def test_resolve_customer_key_rejects_bad_input(key_hex):
    with pytest.raises(SystemExit) as exc:
        with redirect_stdout(io.StringIO()):
            m.resolve_customer_key(key_hex, None)
    assert exc.value.code != 0


@pytest.mark.parametrize("hexseed", ["00" * 20, "00" * 16, "0000", "00"])
def test_pad_seed_all_zero_clears_for_any_length(hexseed):
    # #6: an all-zero seed of ANY length is the delete sentinel -> zero-padded,
    # and the result must be entirely zero (a genuine clear).
    padded = m.pad_seed(unhexlify(hexseed))
    assert len(padded) % 16 == 0
    assert padded == b"\x00" * len(padded)


def test_pad_seed_nonzero_uses_iso_padding():
    raw = unhexlify("DEADBEEFDEADBEEF")
    assert m.pad_seed(raw) == raw + b"\x80" + b"\x00" * 7


def test_pad_title_pads_to_block():
    assert len(m.pad_title(b"Google")) == 16
    assert m.pad_title(b"Google") == b"Google" + b"\x80" + b"\x00" * 9


def test_build_config_tlv_pinned():
    tlv = m.build_config_tlv(1700000000, 2, 1, "06", 1)
    assert tlv.hex() == "81141f01020f046553f10086090a01010b01060d011e"


def test_build_sync_tlv_pinned():
    assert m.build_sync_tlv(1700000000).hex() == "81060f046553f100"


# ---------------------------------------------------------------------------
# Per-operation APDU construction (mock connection)
# ---------------------------------------------------------------------------

class MockConn:
    """Records transmitted APDUs and returns a fixed status word."""

    def __init__(self, sw1=0x90, sw2=0x00):
        self.apdus = []
        self.sw1 = sw1
        self.sw2 = sw2

    def transmit(self, apdu):
        self.apdus.append(list(apdu))
        return ([], self.sw1, self.sw2)


def _run(fn, *args, sw1=0x90):
    conn = MockConn(sw1=sw1)
    with redirect_stdout(io.StringIO()):
        fn(conn, *args)
    return conn.apdus


def test_set_title_apdu_matches_independent_construction():
    args = Namespace(title="Google", profile="2")
    got = _run(m.set_title, KEY, "02", 2, args)[-1]

    t = b"Google"
    t += b"\x80" + b"\x00" * (15 - len(t) % 16)
    enc = SM4Key(KEY).encrypt(t)
    mac = m.calc_mac(KEY, unhexlify("80D50002" + "10") + enc)
    expected = [0x84, 0xD5, 0x00, 2, len(enc + mac)] + list(enc + mac)
    assert got == expected


def test_set_title_long_title_uses_dynamic_lc():
    # #5: a title that encrypts to two blocks must set Lc from the real size,
    # not a hardcoded 0x14. (17 bytes -> 32 after 0x80 padding; main() rejects
    # >12 bytes, but set_title itself must build the APDU correctly.)
    long_title = "a" * 17
    args = Namespace(title=long_title, profile="2")
    got = _run(m.set_title, KEY, "02", 2, args)[-1]
    enc = SM4Key(KEY).encrypt(m.pad_title(long_title.encode("utf-8")))
    assert len(enc) == 32
    assert got[4] == len(enc) + 4  # Lc reflects 32-byte block + 4-byte MAC (0x24)


def test_apply_config_apdu_matches_independent_construction():
    args = Namespace(timevalue=1700000000, display_timeout="2", algorithm="1",
                     timestep="1", otpdigits="6", profile="2")
    got = _run(m.apply_config, KEY, "02", 2, args)[-1]

    tlv = unhexlify("81141f01020f046553f10086090a01010b01060d011e")
    d_len = hex(len(tlv))[2:].zfill(2)  # 22 bytes -> "16"
    mac = m.calc_mac(KEY, unhexlify("80D40102" + d_len) + tlv)
    expected = [0x84, 0xD4, 0x01, 2, len(tlv + mac)] + list(tlv + mac)
    assert got == expected


def test_sync_time_apdu_matches_independent_construction():
    m.timestamp = lambda: 1700000000
    args = Namespace(synctime=True, synctimeall=False, profile="2")
    got = _run(m.sync_time, KEY, args)[-1]

    tlv = unhexlify("81060f046553f100")
    mac = m.calc_mac(KEY, unhexlify("80D40102" + "08") + tlv)
    expected = [0x84, 0xD4, 0x01, 2, len(tlv + mac)] + list(tlv + mac)
    assert got == expected


def test_write_seed_delete_path_apdu():
    args = Namespace(profile="2")
    got = _run(m.write_seed, KEY, "02", 2, "00" * 20, args)[-1]

    padded = unhexlify("00" * 20) + b"\x00" * (16 - 20 % 16)
    enc = SM4Key(KEY).encrypt(padded)
    add_len = hex(len(enc))[2:].zfill(2)
    mac = m.calc_mac(KEY, unhexlify("80C50102" + add_len) + enc)
    expected = [0x84, 0xC5, 0x01, 2, len(enc + mac)] + list(enc + mac)
    assert got == expected


def test_set_customer_key_apdu():
    args = Namespace(setkey="00" * 16, setkeyascii=None)
    got = _run(m.set_customer_key, KEY, args)[-1]

    nk = hashlib.sha1(unhexlify("00" * 16)).digest()[:16]
    enc = SM4Key(KEY).encrypt(unhexlify("00") + nk + unhexlify("80" + "00" * 14))
    mac = m.calc_mac(KEY, unhexlify("80d7000020") + enc)
    expected = [0x84, 0xD7, 0x00, 0x00, 0x24] + list(enc + mac)
    assert got == expected


# ---------------------------------------------------------------------------
# Failure handling (#3 / #4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn,args", [
    (m.write_seed, (KEY, "02", 2, "00" * 20, Namespace(profile="2"))),
    (m.set_title, (KEY, "02", 2, Namespace(title="x", profile="2"))),
    (m.apply_config, (KEY, "02", 2, Namespace(timevalue=1700000000, display_timeout="2",
                                              algorithm="1", timestep="1", otpdigits="6", profile="2"))),
    (m.lock_screen, ()),
    (m.unlock_screen, ()),
    (m.delete_seed, (Namespace(profile="2"), 2)),
])
def test_operations_exit_nonzero_on_bad_status(fn, args):
    # #3: a rejected command (non-0x90 status) must abort with a non-zero exit.
    with pytest.raises(SystemExit) as exc:
        _run(fn, *args, sw1=0x6A)
    assert exc.value.code != 0


def test_set_title_success_does_not_exit():
    with redirect_stdout(io.StringIO()):
        m.set_title(MockConn(sw1=0x90), KEY, "02", 2, Namespace(title="x", profile="2"))


def test_authenticate_fails_closed_on_unexpected_status():
    # #4: the handshake must abort on any status word other than 0x90 / 0x63.
    class AuthConn:
        def __init__(self):
            self.n = 0

        def transmit(self, apdu):
            self.n += 1
            # 1st transmit = challenge request (8 bytes, OK); 2nd = response.
            return ([0] * 8, 0x90, 0x00) if self.n == 1 else ([], 0x6A, 0x82)

    with pytest.raises(SystemExit) as exc:
        with redirect_stdout(io.StringIO()):
            m.authenticate(AuthConn(), KEY)
    assert exc.value.code != 0
