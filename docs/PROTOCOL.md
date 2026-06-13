# Token2 Molto2v2 wire protocol

This document describes the wire protocol the Molto2 device speaks, as
implemented by `molto2.py` in this repository. It is intended so contributors
can work on the tool without reverse-engineering the device themselves. Every
fact here describes behaviour of the Token2 device itself.

> **Status:** the APDU layouts and the SM4/MAC construction below are taken
> directly from the working `molto2.py` script and are byte-for-byte what the
> tool transmits. Response layouts (notably `get info`) are parsed by the
> script but the meaning of a few header/separator bytes is inferred rather
> than documented by the vendor — these are flagged under "Known unknowns".

## Transport

- **Class:** USB CCID smart card (ISO 7816-4 APDUs over PC/SC).
- **Vendor ID:** `0x349E`
- **Product ID:** `0x0300`
- **Reader name hint:** "TOKEN2" (case-insensitive substring match).
- On Linux the device must be added to libccid's `Info.plist` so that pcscd
  picks it up. See the README for the exact `ifdVendorID` / `ifdProductID` /
  `ifdFriendlyName` entries.

## Cryptographic primitives

| Primitive | Purpose |
| --- | --- |
| **SM4** (GB/T 32907-2016, 128-bit block, 128-bit key) | Encrypts seeds, titles, and the auth response; provides the per-command MAC |
| **SHA-1** (RFC 3174) | Derives the SM4 key from the customer key |
| **base32** (RFC 4648) | Optional input encoding for TOTP secrets; the wire format is raw bytes |

The device's SM4 key is derived as `SHA1(customer_key)[..16]`. The default
customer key on a factory-fresh device is the 16-byte ASCII string
`TOKEN2MOLTO1-KEY` (hex `544F4B454E324D4F4C544F312D4B4559`), which derives the
SM4 key:

```
09 92 50 fd b0 17 f4 42 da 42 9e cb be e1 7f 79
```

A customer key may be supplied to the tool either as 16 raw bytes in hex
(`--key`) or as a 16-character ASCII string (`--keyascii`); both are hashed the
same way to produce the SM4 key.

## Authentication handshake

Required before any "secure" command (CLA `0x84`) and before lock/unlock and
delete-seed.

1. Host sends `80 4B 08 00 00` to read an 8-byte challenge.
2. Device responds with 8 random bytes + `SW=9000`.
3. Host zero-pads the challenge to 16 bytes, SM4-ECB-encrypts it with the
   derived key, and sends `80 CE 00 00 10 <16-byte ciphertext>`.
4. On success the device returns `SW=9000`. On failure it returns `SW=63 NN`,
   where `NN` (`sw2`) is the number of attempts remaining before the device
   locks.

## Per-command MAC (secure commands)

Every CLA `0x84` command carries a trailing 4-byte MAC inside its payload. The
MAC is computed as:

1. Build the MAC input: `[CLA=0x80, INS, P1, P2, Lc'] || payload`, where `Lc'`
   is the length of the **payload only** (the encrypted/plaintext body, *not*
   including the 4-byte MAC), and `payload` is that body.
2. Apply ISO/IEC 9797-1 padding method 2 ("`0x80` then zeros to a 16-byte
   boundary"), but **only if the input is not already block-aligned**. If it is
   already a multiple of 16 bytes, no padding block is appended.
3. SM4-CBC encrypt the padded input with IV = 16 zero bytes.
4. The MAC is the first 4 bytes of the **last** ciphertext block.

Note that step 1 uses `0x80` (the *plain* class byte) in the MAC header even
though the transmitted APDU uses `0x84`. The transmitted `Lc` is the length of
the full payload (body + 4-byte MAC).

## Command catalog

In the tables below "Lc" is the length of the entire payload (body + MAC where
applicable). All multi-byte numbers are big-endian unless noted.

### Plain commands (CLA `0x80`, no auth, no MAC)

| INS | P1 | P2 | Payload | Returns | Description |
| --- | --- | --- | --- | --- | --- |
| `0x41` | `00` | `00` | — (Le=`00`) | Device info | Serial + system time |
| `0x41` | `00` | profile | `70` (1 byte, TLV tag) | Public data TLV | Read public profile data (seed-exists flag) |
| `0x4B` | `08` | `00` | — (Le=`00`) | 8-byte challenge | Start auth handshake |
| `0xCE` | `00` | `00` | 16-byte SM4(challenge \|\| zeros) | — | Finish auth handshake |
| `0x56` | `00` | `00` | — (Le=`00`) | — | Factory reset (physical confirm) |

#### `0x41` get-info response layout

```
offset  length  field
0       3       (device-specific header)
3       1       serial-string length N
4       N       serial number, ASCII
4+N     2       (separator)
6+N     4       UTC time as a big-endian u32 (unix epoch seconds)
```

#### `0x41` public-data response layout (seed-exists check)

When called with P2 = profile number and a 1-byte payload of `0x70`, the device
returns a TLV nested under tag `0x95` (`TLV_TAG_PUBLIC_DATA`):

```
95 <len>
   70 <len>                 (TLV_TAG_SEED_INFO)
      <flag      1 byte>
      <tips      16 bytes>
      <RTCTime   4 bytes>
      <TimeCfg   4 bytes>
      <OtpAlg    1 byte>
      <OtpStep   1 byte>
      <OtpLen    1 byte>
      <SeedExist 1 byte>    00 = no seed, 01 = seed present
```

The tool reads `SeedExist` (the last byte of the `0x70` value) to refuse
overwriting a profile that already holds a seed.

### Secure commands (CLA `0x84`, MAC required)

| INS | P1 | P2 | Body | Purpose |
| --- | --- | --- | --- | --- |
| `0xC5` | `01` | profile | SM4-ECB(seed, padded) | Write a profile seed |
| `0xD5` | `00` | profile | SM4-ECB(title bytes, padded to 16) | Write a profile title (≤12 bytes) |
| `0xD4` | `01` | profile | plaintext TLV (see below) | Write profile config / sync time |
| `0xD7` | `00` | `00` | SM4-ECB(`00 \|\| sha1(new_key)[..16] \|\| 80 \|\| 14×00`) | Rotate customer key (physical confirm) |

Seed payloads accept 1..63 raw bytes; the host pads with `0x80` then zeros to a
16-byte boundary before SM4 encryption. The all-zero seed is a special case
used to clear a slot: it is zero-padded (no `0x80`) instead.

Title payloads accept 1..12 UTF-8 bytes; the host applies `0x80`/zero padding so
the encrypted body is exactly 16 bytes.

### Config TLV (`INS 0xD4 P1=0x01`)

The body of the config command is a plaintext TLV (not encrypted) followed by
the 4-byte MAC. The full config TLV is:

```
81 14
   1F 01 <display_timeout: 0=15s, 1=30s, 2=60s, 3=120s>
   0F 04 <UTC time u32 BE>
   86 09
      0A 01 <hmac_algo: 1=SHA1, 2=SHA256>
      0B 01 <digits: 04, 06, 08, or 0A>
      0D 01 <time_step: 0x1E for 30s, 0x3C for 60s>
```

The sync-time slim variant uses just:

```
81 06
   0F 04 <UTC time u32 BE>
```

with the same `D4 01 <profile>` header. `--synctimeall` repeats this for every
profile slot.

### Delete seed (`INS 0xE6`)

`84 E6 00 <profile> 00` clears the seed on a profile while keeping its other
settings. It must be sent on an authenticated session (after the `0xCE`
handshake). No body is sent.

### Screen lock / unlock (`INS 0xD8`, v2.1+)

| Operation | APDU |
| --- | --- |
| Lock | `80 D8 0C 02 00` |
| Unlock | `80 D8 0C 02 01 01` (Lc=`01`, data byte `01`) |

The lock command carries no data. The unlock command carries a single data
byte. These are only supported on firmware v2.1 and higher.

## Status words

| SW | Meaning |
| --- | --- |
| `9000` | Success — command completed |
| `63 NN` | Auth failed; `NN` (sw2) is attempts remaining before lock |
| other `6xxx` / `9xxx` | Command-specific failure |

For the operations that require a physical button press (factory reset, set
customer key), the device accepts the request over the wire and then waits for
the user to press the up-arrow (▲) button to commit the change.

## Important


1. **Firmware variance.** Lock/unlock (`0xD8`) is implemented  as v2.1+.  

 
