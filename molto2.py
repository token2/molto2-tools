#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Token2 Molto2 USB Config Tool, Python version, v0.2
# Copyright (c) 2023-2026 Token2 Sarl
# Released under the MIT License. See LICENSE.md for details.
#
# This module is importable: importing it has no side effects (it does not
# parse arguments, touch the device, or print anything). The CLI behaviour
# lives in main(), guarded by `if __name__ == "__main__"`. The pure helpers
# (calc_mac, derive_session_key, pad_seed, pad_title, build_config_tlv,
# build_sync_tlv, base32_to_hex) can be imported and unit-tested without a
# device.


import sys
from smartcard.System import readers
from binascii import unhexlify, hexlify
from datetime import datetime
import hashlib
import base64
from sm4 import SM4Key
from time import time as timestamp
import argparse

DEFAULT_CUSTOMER_KEY = "544F4B454E324D4F4C544F312D4B4559"


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, no device — safe to import and unit-test)
# ---------------------------------------------------------------------------

def success(sw1):
    return sw1 == 144


def calc_mac(key, message: bytes) -> bytes:
    message_with_padding = message
    if len(message) % 16 != 0:
        message_with_padding += b'\x80' + b'\x00' * (15 - len(message) % 16)

    sm4 = SM4Key(key)
    mac = sm4.encrypt(message_with_padding, initial=b'\0' * 16)
    mac = mac[-16:-16 + 4]  # MAC is the first 4 bytes (of the last block).

    return mac


def derive_session_key(customer_key: bytes) -> bytes:
    """Derive the 16-byte SM4 session key from the customer key."""
    return hashlib.sha1(customer_key).digest()[:16]


def base32_to_hex(seedbase32: str) -> str:
    """Convert a base32 seed (RFC 4648, padding optional) to an uppercase hex string."""
    normalized_seed32 = str(seedbase32 + '=' * (-len(seedbase32) % 8))
    return base64.b16encode(base64.b32decode(normalized_seed32)).decode("utf-8")


def pad_seed(seed_bytes: bytes) -> bytes:
    """Pad a raw seed to a 16-byte boundary for SM4 encryption.

    An all-zero seed of any length is the reserved "clear" value and is
    zero-padded (no 0x80 marker); every other seed gets the 0x80 / zero
    ISO padding.
    """
    if seed_bytes == b'\x00' * len(seed_bytes):
        return seed_bytes + b'\x00' * (16 - len(seed_bytes) % 16)
    return seed_bytes + b'\x80' + b'\x00' * (15 - len(seed_bytes) % 16)


def pad_title(title_bytes: bytes) -> bytes:
    """Pad a UTF-8 title to a 16-byte boundary for SM4 encryption."""
    if len(title_bytes) % 16 != 0:
        return title_bytes + b'\x80' + b'\x00' * (15 - len(title_bytes) % 16)
    return title_bytes


def build_config_tlv(time_val, display_timeout, hmac_method, otp_digits_hex, time_step) -> bytes:
    """Build the plaintext configuration TLV (without the trailing MAC)."""
    time_hex = hex(time_val)[2:].zfill(8)
    dt_hex = "0" + str(display_timeout)
    hmac_hex = "0" + str(hmac_method)
    tstep_hex = "1E" if time_step == 1 else "3C"

    data = "8114"  # TLV_TAG_SYS_CONFG header and length
    data = data + "1F01" + dt_hex          # TLV_TAG_SYSCLOSE_TIMEOUT header and length
    data = data + "0F04" + time_hex        # TLV_TAG_UTC_TIME header and length
    data = data + "8609"                   # TLV_TAG_TOTP_PARAM header and length
    data = data + "0A01" + hmac_hex        # TLV_TAG_TOTP_HMAC header and length
    data = data + "0B01" + otp_digits_hex  # TLV_TAG_OCRA_TRUNC_LEN header and length
    data = data + "0D01" + tstep_hex       # TLV_TAG_TOTP_TIME_STEP header and length

    return unhexlify(data)


def build_sync_tlv(time_val) -> bytes:
    """Build the reduced time-sync TLV (without the trailing MAC)."""
    time_hex = hex(time_val)[2:].zfill(8)
    data = "8106"               # TLV_TAG_SYS_CONFG header and length
    data = data + "0F04" + time_hex  # TLV_TAG_UTC_TIME header and length
    return unhexlify(data)


# ---------------------------------------------------------------------------
# Device helpers (require a PC/SC connection)
# ---------------------------------------------------------------------------

def die(message):
    print("[!] " + message)
    sys.exit(1)  # ← was exit() with no arg = code 0 = fake success


def find_token2_reader():
    return next((reader for reader in readers()
                 if "TOKEN2".lower() in reader.name.lower()), None)


def connect():
    """Locate the Token2 reader and open a connection, or exit with an error."""
    reader = find_token2_reader()

    if reader is None:
        print("[!] No TOKEN2 Molto2 reader found.")
        print("[!] Make sure the device is plugged in and PCSC is configured")
        print("    (see the README for the ifd-ccid.bundle / Info.plist setup).")
        sys.exit(1)

    try:
        connection = reader.createConnection()
        connection.connect()
    except Exception as exc:
        print(f"[!] Could not connect to the device: {exc}")
        print("[!] Check that pcscd is running and no other app holds the device.")
        sys.exit(1)

    return connection


def read_device_info(connection):
    """Read the serial number and system time (UTC) from the device."""
    SELECT = [0x80, 0x41, 0x00, 0x00, 0x00]
    data, sw1, _sw2 = connection.transmit(SELECT)
    info = bytes(data)
    serial_len = int(info[3])
    serial = info[4:4 + serial_len].decode("utf-8")
    time_offset = 4 + serial_len + 2
    time_len = 4
    time = int.from_bytes(info[time_offset:time_offset + time_len], "big")
    time = datetime.utcfromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S")
    return serial, time


def authenticate(connection, key_sha1):
    """Run the challenge-response handshake; exits on failure."""
    SELECT = [0x80, 0x4b, 0x08, 0x00, 0x00]
    data, sw1, _sw2 = connection.transmit(SELECT)
    challenge = bytes(data)
    challenge = challenge + b'\x00' * 8
    sm4 = SM4Key(key_sha1)
    response_raw = sm4.encrypt(challenge)
    apdu = [0x80, 0xCE, 0x00, 0x00, 0x10]
    apdu.extend(response_raw)
    _data, sw1, sw2 = connection.transmit(apdu)
    if sw1 == 99:
        print(f"[-] Authentication failure, number of attempts left: {sw2}")
        die(f"[-] Make sure you entered the correct access key / password")
    if success(sw1):
        print(f"[+] Authentication successful")
    else:
        # Fail closed: any status word other than 0x90 / 0x63 means we are
        # NOT authenticated. Do not fall through to secure commands.
        die(f"[-] Authentication returned unexpected status {hex(sw1)} {hex(sw2)}")


def profile_has_seed(connection, profile_num):
    """
    Uses Read Public Data (INS 0x41) with TLV_TAG_SEED_INFO (0x70)
    to check if a seed exists on the given profile.
    Per manual 7.1: SeedExist byte: 00 = does not exist, 01 = exists.
    No authentication required.
    """
    cla = 0x80
    ins = 0x41
    p1 = 0x00
    p2 = profile_num
    lc = 0x01
    data = [0x70]  # TLV_TAG_SEED_INFO
    apdu = [cla, ins, p1, p2, lc] + data
    resp, sw1, sw2 = connection.transmit(apdu)

    print(f"[i] Profile #{profile_num} seed info: SW1={hex(sw1)}, SW2={hex(sw2)}, raw={bytes(resp).hex()}")

    if not success(sw1):
        print(f"[-] Profile #{profile_num} read failed: {hex(sw1)}{hex(sw2)}")
        return False

    resp_bytes = bytes(resp)

    # Response is TLV nested under TLV_TAG_PUBLIC_DATA (0x95)
    # Structure: 95 <len> 70 <len> <flag 1B> <tips 16B> <RTCTime 4B> <TimeCfg 4B>
    #            <OtpAlgOtp 1B> <OtpStep 1B> <OtpLen 1B> <SeedExist 1B>
    # SeedExist is the last byte of TLV_TAG_SEED_INFO value = offset 1+1+1+1+1+16+4+4+1+1+1 = 28 from tag 0x70
    try:
        # Find TLV_TAG_PUBLIC_DATA (0x95)
        if resp_bytes[0] != 0x95:
            print(f"[-] Unexpected outer tag: {hex(resp_bytes[0])}")
            return False
        # outer_len = resp_bytes[1]
        inner = resp_bytes[2:]

        # Find TLV_TAG_SEED_INFO (0x70) inside
        idx = 0
        while idx < len(inner):
            tag = inner[idx]
            length = inner[idx + 1]
            value = inner[idx + 2: idx + 2 + length]
            if tag == 0x70:
                # SeedExist is the last byte of the value
                seed_exist = value[-1]
                print(f"[i] SeedExist byte: {hex(seed_exist)}")
                return seed_exist == 0x01
            idx += 2 + length

        print(f"[-] TLV_TAG_SEED_INFO (0x70) not found in response")
        return False

    except IndexError:
        print(f"[-] Failed to parse TLV response for profile #{profile_num}")
        return False


# ---------------------------------------------------------------------------
# Operations (each issues one command family on an authenticated session)
# ---------------------------------------------------------------------------

def factory_reset(connection):
    SELECT = [0x80, 0x56, 0x00, 0x00, 0x00]
    _data, sw1, _sw2 = connection.transmit(SELECT)
    print(f"[i] Factory reset")
    print(f"[i] Resetting the device to factory settings. Please note that this will delete all profiles and set the customer key to default")
    die(f"[!] PLEASE CONFIRM THE CHANGE ON THE DEVICE BY PRESSING the ▲ KEY!")


def delete_seed(connection, args, profile_number):
    if args.profile is None:
        die("[x] No profile number provided. Please supply --profile.")
    print(f"[i] Deleting seed for profile [#{args.profile}]...")
    cla = 0x80
    ins = 0xE6
    p1 = 0x00
    p2 = profile_number
    lc = 0x00
    apdu = [cla, ins, p1, p2, lc]
    _data, sw1, _sw2 = connection.transmit(apdu)
    if success(sw1):
        print(f"[+] Seed deleted successfully for profile [#{args.profile}]")
    else:
        die(f"[!] Seed delete failed for profile [#{args.profile}] SW: {hex(sw1)}{hex(_sw2)}")


def lock_screen(connection):
    print("[i] Locking device screen")
    cla = 0x80
    ins = 0xD8
    p1 = 0x0C
    p2 = 0x02
    lc = 0x00
    apdu = [cla, ins, p1, p2, lc]

    _data, sw1, _sw2 = connection.transmit(apdu)

    if success(sw1):
        print(f"[+] Device screen locked")
    else:
        die(f"[!] Lock failed (SW={hex(sw1)}{hex(_sw2)})")


def unlock_screen(connection):
    print("[i] Unlocking device screen")
    cla = 0x80
    ins = 0xD8
    p1 = 0x0C
    p2 = 0x02
    lc = 0x01
    data = 0x01
    apdu = [cla, ins, p1, p2, lc, data]

    _data, sw1, _sw2 = connection.transmit(apdu)

    if success(sw1):
        print(f"[+] Device screen unlocked")
    else:
        die(f"[!] Unlock failed (SW={hex(sw1)}{hex(_sw2)})")


def write_seed(connection, key_sha1, prof, profile_number, seed, args):
    if len(seed) % 2 != 0:
        die("[!] Seed hex-string has an invalid length (not multiple of 2 chars.)")
    if len(seed) > 63 * 2:
        die("[!] Seed is too long (more than 63 bytes)")

    seed_bytes = unhexlify(seed)
    is_deleting = seed_bytes == b'\x00' * len(seed_bytes)

    if not is_deleting:
        print(f"[i] Checking if profile [#{args.profile}] already has a seed...")
        if profile_has_seed(connection, profile_number):
            die(f"[x] Profile #{args.profile} already has a seed. "
                f"Delete it first using --seed {'00' * 20} or the --deleteseed command.")
        print(f"[+] Profile [#{args.profile}] is empty. Proceeding with seed write.")
    else:
        print(f"[i] Deleting seed on profile [#{args.profile}] — skipping existence check.")

    print(f"[i] Writing seed:  '{seed.upper()}'  for profile [#{args.profile}] ")
    seed = pad_seed(unhexlify(seed))
    print(f"[i] adjusted seed: '{hexlify(seed).decode('utf-8').upper()}'")

    sm4 = SM4Key(key_sha1)
    enc_seed = sm4.encrypt(seed)
    mac_seed = len(enc_seed)
    add_len = hex(mac_seed)[2:].zfill(2)
    mac_packet = unhexlify("80C501" + prof + add_len) + enc_seed
    mac = calc_mac(key_sha1, mac_packet)
    cla = 0x84
    ins = 0xC5
    p1 = 0x01
    p2 = profile_number
    data = enc_seed + mac
    lc = len(data)
    apdu = [cla, ins, p1, p2, lc]
    apdu.extend(data)
    _data, sw1, _sw2 = connection.transmit(apdu)
    if success(sw1):
        print(f"[+] Seed was set successfully")
    else:
        die(f"[!] Seed write failed for profile [#{args.profile}] (SW={hex(sw1)}{hex(_sw2)})")


def set_title(connection, key_sha1, prof, profile_number, args):
    print(f"[i] Setting profile title as '{args.title}' for profile [#{args.profile}]")
    cla = 0x84
    ins = 0xD5
    p1 = 0x00
    p2 = profile_number
    sm4 = SM4Key(key_sha1)
    title = pad_title(args.title.encode("utf-8"))
    # print  (f"Setting title {title}")
    enc_title = sm4.encrypt(title)
    # Derive the MAC header length and Lc from the actual encrypted size
    # instead of hardcoding a single 16-byte block.
    enc_len = hex(len(enc_title))[2:].zfill(2)
    mac_packet = unhexlify("80D500" + prof + enc_len) + enc_title
    mac = calc_mac(key_sha1, mac_packet)
    data = enc_title + mac
    lc = len(data)
    apdu = [cla, ins, p1, p2, lc]
    apdu.extend(data)

    _data, sw1, _sw2 = connection.transmit(apdu)
    if success(sw1):
        print(f"[+] Title was set successfully")
    else:
        die(f"[!] Title write failed for profile [#{args.profile}] (SW={hex(sw1)}{hex(_sw2)})")


def apply_config(connection, key_sha1, prof, profile_number, args):
    print("[i] Setting configuration")

    # Get current time
    time = int(args.timevalue) if args.timevalue is not None else int(timestamp())

    display_timeout = int(args.display_timeout or 99)
    if display_timeout > 3 or display_timeout < 0:
        die("[!] Incorrect display_timeout value (must be 0-3).")

    hmac_method = int(args.algorithm or 99)
    if hmac_method > 2 or hmac_method < 1:
        die("[!] Incorrect algorithm (must be 1 for sha1 or 2 for sha256)")

    time_step = int(args.timestep or 99)
    if time_step > 2 or time_step < 1:
        die("Incorrect timestep value provided (must be 1 for 30s or 2 for 60s).")

    if args.otpdigits is None:
        otp_digits = "6"
    else:
        otp_digits = str(args.otpdigits)

    otp_digits_map = {"4": "04", "6": "06", "8": "08", "10": "0A"}
    if otp_digits not in otp_digits_map:
        die("[!] Incorrect otpdigits value (must be 4, 6, 8 or 10).")
    otp_digits_hex = otp_digits_map[otp_digits]

    # Construct command data
    data = build_config_tlv(time, display_timeout, hmac_method, otp_digits_hex, time_step)

    mac_d = len(data)
    d_len = hex(mac_d)[2:].zfill(2)

    mac_packet = unhexlify("80D401" + prof + d_len) + data
    mac = calc_mac(key_sha1, mac_packet)

    cla = 0x84
    ins = 0xD4
    p1 = 0x01
    p2 = profile_number
    data = data + mac
    lc = len(data)

    apdu = [cla, ins, p1, p2, lc]
    apdu.extend(data)

    _data, sw1, _sw2 = connection.transmit(apdu)

    if success(sw1):
        print(f"[+] Config was set successfully for profile [#{args.profile}]")
    else:
        die(f"[!] Config failed for [#{args.profile}] (SW={hex(sw1)}{hex(_sw2)})")


def set_customer_key(connection, key_sha1, args):
    hexkey = ""

    if args.setkey is not None:
        hexkey = args.setkey.upper()
        print(f"[i] Setting new customer key hex value as: {hexkey}")

    if args.setkeyascii is not None:
        hexkey = args.setkeyascii.encode('utf-8').hex().upper()
        print(f"[i] Setting new customer key (ASCII):  {args.setkeyascii}")
        print(f"[i] New customer key hex value is: {hexkey}")

    if hexkey != "":
        # set customer key
        print(f"[i] Setting new key ")
        newkey_sha1 = hashlib.sha1(unhexlify(hexkey)).digest()[:16]
        encData = unhexlify("00") + newkey_sha1 + unhexlify("800000000000000000000000000000")
        sm4 = SM4Key(key_sha1)
        SM4encData = sm4.encrypt(encData)
        mac_packet = unhexlify("80d7000020") + SM4encData
        mac = calc_mac(key_sha1, mac_packet)
        cla = 0x84
        ins = 0xD7
        p1 = 0x00
        p2 = 0x00
        lc = 0x24
        data = SM4encData + mac
        apdu = [cla, ins, p1, p2, lc]
        apdu.extend(data)
        _data, sw1, _sw2 = connection.transmit(apdu)
        if success(sw1):
            print(f"[+] New customer key request was successfully sent to the device.")
            print(f"[!] Complete the operation by confirming on the device.")
            print(f"[!] You need to press the up arrow (▲) button for confirmation")
        else:
            die(f"[!] Set customer key failed (SW={hex(sw1)}{hex(_sw2)})")


def sync_time(connection, key_sha1, args):
    if args.synctime is True:
        print(f"[i] Syncing time on profile [#{args.profile}]")
        sync_profiles = [args.profile]
    if args.synctimeall is True:
        print(f"[i] Syncing time on all profiles")
        sync_profiles = range(100)

    sync_had_error = False
    for profnumber in sync_profiles:
        profile_number = int(profnumber)
        prof = hex(profile_number)[2:].zfill(2)
        print(f"Syncing time for profile #{profile_number}")
        # Get current time
        time = int(timestamp())
        # Construct command data
        data = build_sync_tlv(time)
        mac_d = len(data)
        d_len = hex(mac_d)[2:].zfill(2)
        mac_packet = unhexlify("80D401" + prof + d_len) + data
        mac = calc_mac(key_sha1, mac_packet)
        cla = 0x84
        ins = 0xD4
        p1 = 0x01
        p2 = profile_number
        data = data + mac
        lc = len(data)
        apdu = [cla, ins, p1, p2, lc]
        apdu.extend(data)
        _data, sw1, _sw2 = connection.transmit(apdu)

        if success(sw1):
            print(f"[+] Time was set successfully for profile [#{profile_number}]")
        else:
            print(f"[!] Time sync failed for  [#{profile_number}] (SW={hex(sw1)}{hex(_sw2)})")
            sync_had_error = True

    if sync_had_error:
        die("[!] One or more profiles failed to time-sync.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", help="Customer key in hex format. Default will be used if not supplied.")
    parser.add_argument("--keyascii", help="Customer key in ascii format. Default will be used if not supplied.")
    parser.add_argument("--profile", help="Profile number, from 0 to 49 (Molto2) or from 0 to 99 (Molto2 v2)")
    parser.add_argument("--title", help="Profile title, 12 chars max")
    parser.add_argument("--seed", help="Seed to write, in hex format")
    parser.add_argument("--seedbase32", help="Seed to write, in base32 format")
    parser.add_argument("--setkey",
                        help="Set the new customer key, providing the key  in hex. Please note that setting new key requires confirmation on the device (physical button press)")
    parser.add_argument("--setkeyascii",
                        help="Set the new customer key, providing key in ascii. Please note that setting new key requires confirmation on the device (physical button press)")
    parser.add_argument("--config", help="If config parameter is set, the config parameters become required.",
                        action='store_true')
    parser.add_argument("--synctime", help="Will update time on the given profile.", action='store_true')
    parser.add_argument("--synctimeall", help="Will update time on all profiles.", action='store_true')
    parser.add_argument("--display_timeout",
                        help="mandatory if --config is set as 1. Possible values 0=15s, 1=30s, 2=60s, 3=120s")
    parser.add_argument("--algorithm",
                        help="mandatory if --config is set as 1. Possible values 1=SHA1 HMAC or 2=SHA256 HMAC hashing algorithm")
    parser.add_argument("--timestep",
                        help="mandatory if --config is set as 1. Possible values 1=30 seconds   or 2= 60 seconds")
    parser.add_argument("--otpdigits",
                        help="Number of digits generated by TOTP algorithm. Possible values 4, 6, 8 or 10. Default is 6.")
    parser.add_argument("--factoryreset",
                        help="Resets the device to factory setting and clear all data. Please note this requires confirmation on the device (physical button press)",
                        action='store_true')
    parser.add_argument("--lock", help="Lock device screen (only for v2.1 and higher)", action='store_true')
    parser.add_argument("--unlock", help="Unlock device screen (only for v2.1 and higher)", action='store_true')

    parser.add_argument("--deleteseed", help="Delete the OTP seed for the given profile, keeping other config (algorithm, prompts, etc.)", action='store_true')

    parser.add_argument("--timevalue", type=int, help="UNIX timestamp to use instead of current time")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    connection = connect()

    print(f"==========================================================")
    print(f" [i] TOKEN2 Molto2 USB Config Tool, Python version, v0.2")
    print(f"                                         (c) TOKEN2 Sarl ")
    print(f"==========================================================")

    if args.factoryreset is True:
        factory_reset(connection)

    if args.seed is not None and args.seedbase32 is not None:
        die("[!] Seed both in hex and base32 supplied, please provide only one format")

    if args.seed is None and args.seedbase32 is not None:
        seed = base32_to_hex(args.seedbase32)
    else:
        seed = args.seed

    # Check Profile title (12-byte device field; validate encoded byte length,
    # not character count, so multibyte UTF-8 cannot overflow the block).
    if args.title is not None:
        if len(args.title.encode("utf-8")) > 12:
            die("[!] Profile title cannot be longer than 12 bytes (UTF-8)")

    # Default customer key
    if args.key is None and args.keyascii is None:
        customer_key = DEFAULT_CUSTOMER_KEY
        print('[!] Note: No customer key was provided, default customer key will be used')
    else:
        if args.key is not None:
            customer_key = args.key
        if args.keyascii is not None:
            customer_key = args.keyascii.encode('utf-8').hex().upper()

    customer_key = unhexlify(customer_key)

    if args.profile is not None:
        profile_number = int(args.profile)
        prof = hex(profile_number)[2:].zfill(2)
    else:
        profile_number = 0x00
        prof = "00"

    # Get Serial Number
    serial, dev_time = read_device_info(connection)
    print(f"[+] device serial number: {serial}")
    print(f"[+] device system time (UTC): {dev_time}")

    if not args.synctimeall:
        if (args.config or args.seed is not None or args.title is not None or args.synctime) and args.profile is None:
            die("[x] No valid profile number is provided. We don't know which profile to use. Please supply a profile number (0-49 for Molto2 and 0-99 for Molto2 v2)")
    else:
        if args.profile is not None:
            print(f"[i] Selected profile: [#{args.profile}]")

    key_sha1 = derive_session_key(customer_key)
    authenticate(connection, key_sha1)

    # Delete seed (requires an authenticated session)
    if args.deleteseed is True:
        delete_seed(connection, args, profile_number)

    if args.lock is True:
        lock_screen(connection)

    if args.unlock is True:
        unlock_screen(connection)

    if seed is not None:
        write_seed(connection, key_sha1, prof, profile_number, seed, args)

    if args.title is not None:
        set_title(connection, key_sha1, prof, profile_number, args)

    if args.config is True:
        apply_config(connection, key_sha1, prof, profile_number, args)

    set_customer_key(connection, key_sha1, args)

    if args.synctime is True or args.synctimeall is True:
        sync_time(connection, key_sha1, args)


if __name__ == "__main__":
    main()
