# Molto2v2 Wire Protocol Specification

Token2 Sàrl

This document specifies the wire protocol used to configure the Token2 Molto2v2
multi-profile TOTP hardware token over USB. It is the authoritative reference
for the command set implemented by `molto2.py` in this repository and is
provided so that integrators can build compatible tooling.

All commands are ISO 7816-4 APDUs carried over the PC/SC (USB CCID) transport.
Multi-byte integers are big-endian unless stated otherwise.

## 1. Transport

| Property | Value |
| --- | --- |
| Interface class | USB CCID smart card (ISO 7816-4 APDUs over PC/SC) |
| USB Vendor ID | `0x349E` |
| USB Product ID | `0x0300` |
| Reader name | Contains the substring `TOKEN2` (case-insensitive) |

On Linux the device is enumerated through libccid/pcscd. The vendor ID,
product ID and friendly name must be present in libccid's `Info.plist`; see the
README for the required entries.

## 2. Cryptography

| Primitive | Role |
| --- | --- |
| SM4 (GB/T 32907-2016, 128-bit block and key) | Encrypts seeds, titles and the authentication response; computes the per-command MAC |
| SHA-1 (RFC 3174) | Derives the SM4 session key from the customer key |
| base32 (RFC 4648) | Accepted input encoding for TOTP secrets; secrets are transmitted as raw bytes |

### 2.1 Key derivation

The 16-byte SM4 key is derived from the customer key as:

```
sm4_key = SHA1(customer_key)[0..16]
```

The customer key is 16 bytes. It may be supplied as 16 raw bytes (hex) or as a
16-character ASCII string; both are processed identically. The factory-default
customer key is the ASCII string `TOKEN2MOLTO1-KEY` (hex
`54 4F 4B 45 4E 32 4D 4F 4C 54 4F 31 2D 4B 45 59`), which derives the SM4 key:

```
09 92 50 FD B0 17 F4 42 DA 42 9E CB BE E1 7F 79
```

## 3. Authentication

Authentication is required before any secure command (CLA `0x84`) and before
the lock, unlock and delete-seed commands. The handshake is a challenge-response
exchange:

1. The host requests an 8-byte challenge: `80 4B 08 00 00`.
2. The device returns 8 random bytes and `SW=9000`.
3. The host right-pads the challenge to 16 bytes with zeros, encrypts it with
   SM4 (ECB) under the derived key, and sends the 16-byte result:
   `80 CE 00 00 10 <16-byte response>`.
4. The device returns `SW=9000` on success. On failure it returns `SW=63 NN`,
   where `NN` is the number of attempts remaining before the device locks.

## 4. Message authentication code

Each secure command (CLA `0x84`) carries a 4-byte MAC at the end of its payload.
The MAC is computed as follows:

1. Form the MAC input: `[0x80, INS, P1, P2, Lc'] || body`, where `Lc'` is the
   length of `body` only (the encrypted or plaintext payload, excluding the
   4-byte MAC), and `body` is that payload.
2. If the input length is not a multiple of 16 bytes, append `0x80` followed by
   zero bytes up to the next 16-byte boundary. If the input is already a
   multiple of 16 bytes, no padding is added.
3. Encrypt the result with SM4 in CBC mode using an all-zero (16-byte) IV.
4. The MAC is the first 4 bytes of the final ciphertext block.

The MAC header in step 1 always uses class byte `0x80`, even though the
transmitted command uses class byte `0x84`. The `Lc` field of the transmitted
APDU covers the full payload, i.e. `body` plus the 4-byte MAC.

## 5. Command reference

### 5.1 Plain commands (CLA `0x80`)

These commands require neither authentication nor a MAC.

| INS | P1 | P2 | Data | Response | Description |
| --- | --- | --- | --- | --- | --- |
| `0x41` | `00` | `00` | none | Device info | Read serial number and system time |
| `0x41` | `00` | profile | `70` | Public data TLV | Read public profile data (incl. seed-present flag) |
| `0x4B` | `08` | `00` | none | 8-byte challenge | Begin authentication |
| `0xCE` | `00` | `00` | 16-byte response | none | Complete authentication |
| `0x56` | `00` | `00` | none | none | Factory reset (requires on-device confirmation) |

#### Device info response (`0x41`, P2 = `00`)

```
Offset  Length  Field
0       3       Header
3       1       Serial number length, N
4       N       Serial number (ASCII)
4+N     2       Separator
6+N     4       System time, UTC (u32, seconds since the Unix epoch)
```

#### Public data response (`0x41`, P2 = profile, data = `70`)

The response is a TLV structure under tag `0x95` (public data) containing a
nested tag `0x70` (seed info):

```
95 <len>
   70 <len>
      Flag         1 byte
      Tips         16 bytes
      RTC time     4 bytes
      Time config  4 bytes
      OTP algorithm 1 byte
      OTP step      1 byte
      OTP length    1 byte
      Seed present  1 byte   (00 = no seed, 01 = seed present)
```

The seed-present byte is the final byte of the `0x70` value and indicates
whether the addressed profile already holds a seed.

### 5.2 Secure commands (CLA `0x84`)

These commands require a prior authentication handshake and carry a 4-byte MAC.

| INS | P1 | P2 | Body | Description |
| --- | --- | --- | --- | --- |
| `0xC5` | `01` | profile | `SM4-ECB(seed, padded)` | Write a profile seed |
| `0xD5` | `00` | profile | `SM4-ECB(title, padded to 16 bytes)` | Write a profile title (≤12 bytes) |
| `0xD4` | `01` | profile | Plaintext configuration TLV | Write profile configuration / synchronise time |
| `0xD7` | `00` | `00` | `SM4-ECB(00 \|\| SHA1(new_key)[0..16] \|\| 80 \|\| 14×00)` | Change the customer key (requires on-device confirmation) |

**Seed (`0xC5`).** The seed is 1 to 63 raw bytes. The host pads it with `0x80`
followed by zeros to the next 16-byte boundary, then SM4-ECB encrypts it. An
all-zero seed is the reserved value used to clear a profile; in that case the
host zero-pads (without the `0x80` marker) before encryption.

**Title (`0xD5`).** The title is 1 to 12 UTF-8 bytes. The host applies the same
`0x80`/zero padding so the encrypted body is exactly 16 bytes.

### 5.3 Configuration TLV (`0xD4`, P1 = `01`)

The body of the configuration command is a plaintext TLV followed by the 4-byte
MAC. The full configuration TLV is:

```
81 14
   1F 01 <display timeout>     ; 0 = 15s, 1 = 30s, 2 = 60s, 3 = 120s
   0F 04 <UTC time, u32>
   86 09
      0A 01 <HMAC algorithm>   ; 1 = SHA1, 2 = SHA256
      0B 01 <OTP digits>       ; 04, 06, 08 or 0A
      0D 01 <time step>        ; 0x1E = 30s, 0x3C = 60s
```

To synchronise only the device clock, a reduced TLV is used with the same
`D4 01 <profile>` header:

```
81 06
   0F 04 <UTC time, u32>
```

The clock can be synchronised on a single profile or, by repeating the command,
across all profile slots.

### 5.4 Delete seed (`0xE6`)

```
80 E6 00 <profile> 00
```

Clears the seed on the addressed profile while preserving its other settings.
The command carries no body and must be issued on an authenticated session.

### 5.5 Screen lock and unlock (`0xD8`)

| Operation | APDU |
| --- | --- |
| Lock | `80 D8 0C 02 00` |
| Unlock | `80 D8 0C 02 01 01` |

The lock command carries no data. The unlock command carries a single data byte
(`01`). Screen lock and unlock are supported on firmware v2.1 and higher.

## 6. Profiles

The Molto2v2 provides 100 profile slots, addressed by P2 as profile numbers `0`
through `99`. Each profile holds an independent seed, title and TOTP
configuration.

## 7. Status words

| SW | Meaning |
| --- | --- |
| `9000` | Success |
| `63 NN` | Authentication failed; `NN` is the number of attempts remaining before the device locks |
| other | Command-specific failure |

The factory-reset (`0x56`) and customer-key (`0xD7`) commands are accepted over
the wire and then committed only after the user confirms on the device by
pressing the up-arrow (▲) button.
