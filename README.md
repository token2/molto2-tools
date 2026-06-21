Token2 Molto2 USB Config Tool, Python version
=============================================
<img width="350" height="350" alt="image" src="https://github.com/user-attachments/assets/7c631ff7-a69a-417f-b0fd-b21b430b0cc8" />

This is a command line tool to configure the Molto2v2, a multi-profile TOTP
hardware token by [Token2](https://www.token2.swiss/). A simple PyQt5 GUI is also included.

The steps below are written for Ubuntu, but they should be the same or similar on any
other Linux distribution.

Device compatibility
---------------------
This script is developed and tested with the **Molto2 device from Token2** itself.
There may be other "clones" on the market with similar features, but we do not
guarantee that the tool will work with them.

Installation
------------
The script is written for Python 3.

Install the requirements:

    pip install -r requirements.txt

(or `pip3 install -r requirements.txt`). You can also install them one by one:

    pip install pyscard
    pip install sm4

PCSC installation and configuration
-----------------------------------
The tool talks to the device through the PCSC (PC/SC) service. The Python code is
identical on every platform — only the PCSC setup differs. PCSC is available on Linux,
macOS and Windows; follow the section for your operating system below.

The Molto2v2 enumerates with USB vendor ID `0x349E` and product ID `0x0300`. PCSC ships
with a predefined list of supported readers, and as the Molto2v2 is a relatively new
product it is not in that list by default. On Linux it therefore has to be added to the
CCID driver manually (see *Registering the device with the CCID driver* below); on
recent macOS it is often picked up automatically.

### Linux — Debian / Ubuntu

Install the PCSC stack:

    sudo apt-get install libusb-dev libccid pcscd libpcsclite1 libpcsclite-dev pcsc-tools

The `pcscd` daemon is started automatically by the package. The CCID driver list lives
at:

    /usr/lib/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist

### Linux — RHEL / Fedora / Rocky / AlmaLinux

The package names differ from Debian. Install the PCSC stack with `dnf`:

    sudo dnf install pcsc-lite pcsc-lite-ccid pcsc-lite-devel libusb1-devel pcsc-tools

(`pcsc-tools` is optional and may require the EPEL repository on RHEL / Rocky / Alma.)

Enable and start the daemon:

    sudo systemctl enable --now pcscd

On 64-bit RPM distributions the CCID driver list lives under `lib64`:

    /usr/lib64/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist

### macOS

macOS has PCSC built in — there is no daemon to install. Since macOS Sonoma the system
uses the standard CCID driver, and a class-compliant CCID reader like the Molto2 is
often recognised with no configuration at all. First just plug the device in and run:

    python3 molto2.py

If you see the device serial number, you are done — no further setup is needed.

If the device is *not* detected, it has to be registered with the CCID driver. Note that
the system driver bundle at
`/usr/libexec/SmartCardServices/drivers/ifd-ccid.bundle` lives on the SIP-protected,
read-only system volume and **cannot** be edited, even with `sudo`. Instead, register the
device in the user-writable override location:

    # Copy Apple's CCID bundle into the override directory
    sudo mkdir -p /usr/local/libexec/SmartCardServices/drivers
    sudo cp -R /usr/libexec/SmartCardServices/drivers/ifd-ccid.bundle \
               /usr/local/libexec/SmartCardServices/drivers/

    # Edit the COPY (never the system one — that is read-only under SIP)
    sudo nano /usr/local/libexec/SmartCardServices/drivers/ifd-ccid.bundle/Contents/Info.plist

Add the Molto2 IDs as described below, then unplug and re-plug the device (or reboot).

### Windows

Windows ships the Smart Card service (WinSCard) and a built-in CCID driver, so the tool
runs without extra installation. If the device is not recognised, install Token2's
Windows driver / the device's INF as provided by the vendor.

### Registering the device with the CCID driver

When manual registration is required (always on Linux, only if auto-detection fails on
macOS), open the `Info.plist` for your OS shown above and add the Molto2v2 to the three
parallel arrays:

 - Add `<string>0x349E</string>` at the end of the `<key>ifdVendorID</key>` array.
 - Add `<string>0x0300</string>` at the end of the `<key>ifdProductID</key>` array.
 - Add `<string>Token2 Molto2</string>` at the end of the `<key>ifdFriendlyName</key>` array.

These three arrays are positional: the new entry must sit at the **same index** in all
three. Save the file, then apply the change by restarting the PCSC service
(`sudo systemctl restart pcscd` on Linux) or by re-plugging the device / rebooting on
macOS.

(If you cannot locate the file, try `sudo find / -name Info.plist -path '*ifd-ccid*'`.)

Usage
-----
To make sure your system is configured correctly, plug the Molto2 into a USB port and
run the script with no parameters:

    python3 molto2.py

This should produce output similar to the following:

    [i] TOKEN2 Molto2 USB Config Tool, Python version, v0.2
                                             (c) TOKEN2 Sarl
    [!] Note: No customer key was provided, default customer key will be used
    [+] device serial number: 826658719844499
    [+] device system time (UTC): 2022-11-16 09:07:19
    [+] Authentication successful

If you see the serial number of the device, the script has access to it and you can
continue using the tool. The full syntax can be obtained with the `--help` argument:

    python3 molto2.py --help

    usage: molto2.py [-h] [--key KEY] [--keyascii KEYASCII] [--profile PROFILE]
                     [--title TITLE] [--seed SEED] [--seedbase32 SEEDBASE32]
                     [--setkey SETKEY] [--setkeyascii SETKEYASCII] [--config]
                     [--synctime] [--synctimeall] [--display_timeout DISPLAY_TIMEOUT]
                     [--algorithm ALGORITHM] [--timestep TIMESTEP]
                     [--otpdigits OTPDIGITS] [--factoryreset] [--lock] [--unlock]
                     [--deleteseed] [--timevalue TIMEVALUE]

    options:
      -h, --help            show this help message and exit
      --key KEY             Customer key in hex format. Default will be used if not supplied.
      --keyascii KEYASCII   Customer key in ascii format. Default will be used if not supplied.
      --profile PROFILE     Profile number, from 0 to 49 (Molto2) or from 0 to 99 (Molto2 v2)
      --title TITLE         Profile title, 12 chars max
      --seed SEED           Seed to write, in hex format
      --seedbase32 SEEDBASE32
                            Seed to write, in base32 format
      --setkey SETKEY       Set the new customer key, providing the key in hex. Setting a
                            new key requires confirmation on the device (physical button press)
      --setkeyascii SETKEYASCII
                            Set the new customer key, providing the key in ascii. Setting a
                            new key requires confirmation on the device (physical button press)
      --config              If config is set, the config parameters become required.
      --synctime            Update the time on the given profile.
      --synctimeall         Update the time on all profiles.
      --display_timeout DISPLAY_TIMEOUT
                            mandatory if --config is set. Possible values 0=15s, 1=30s, 2=60s, 3=120s
      --algorithm ALGORITHM
                            mandatory if --config is set. Possible values 1=SHA1 HMAC or 2=SHA256 HMAC
      --timestep TIMESTEP   mandatory if --config is set. Possible values 1=30 seconds or 2=60 seconds
      --otpdigits OTPDIGITS
                            Number of digits generated by the TOTP algorithm. Possible
                            values 4, 6, 8 or 10. Default is 6.
      --factoryreset        Reset the device to factory settings and clear all data. Requires
                            confirmation on the device (physical button press)
      --lock                Lock the device screen (only for v2.1 and higher)
      --unlock              Unlock the device screen (only for v2.1 and higher)
      --deleteseed          Delete the OTP seed for the given profile, keeping other config
                            (algorithm, prompts, etc.)
      --timevalue TIMEVALUE
                            UNIX timestamp to use instead of the current time

The following example sets a new hex seed (`--seed DEADBEEFDEADBEEF`) and a configuration
(`--config`) with a TOTP step of 30 seconds (`--timestep 1`), the SHA1 HMAC algorithm
(`--algorithm 1`), a title of 'Google' (`--title Google`) and a display sleep timeout of
60 seconds (`--display_timeout 2`) for profile No.2 (`--profile 2`):

    python3 molto2.py --config --profile 2 --seed DEADBEEFDEADBEEF --timestep 1 --algorithm 1 --display_timeout 2 --title Google

GUI interface
-------------
A simplified GUI built with Qt is also available. Make sure PyQt5 is installed:

    pip install PyQt5

Then launch it from the same directory:

    python3 gui.py

`gui.py` calls `molto2.py` under the hood, so keep both files together. A self-contained
variant, `gui-single.py`, embeds the device logic directly and can be run on its own:

    python3 gui-single.py

Supported products
------------------
* [Token2 Molto2v2]([https://www.token2.com/](https://www.token2.swiss/shop/product/molto-2-v2-multi-profile-totp-programmable-hardware-token))

See the "Device compatibility" note above regarding third-party clones.

Development and tests
---------------------
The device logic in `molto2.py` is importable, so the cryptography and APDU
construction can be unit-tested without a device. The tests need only `sm4`
(no pyscard or hardware):

    pip install -r requirements-dev.txt
    pytest

The same checks (byte-compile, lint, unit tests) run in CI via GitHub Actions
on every push and pull request — see [.github/workflows/ci.yml](.github/workflows/ci.yml).

License
-------
This project is released under the MIT License. See [LICENSE.md](LICENSE.md) for details.

Developed by the Token2 R&D Team (https://www.token2.com/).

Protocol
--------
The device wire protocol (APDUs, SM4/MAC construction, TLV layouts) is
documented in [docs/MOLTO2-PROTOCOL.md](docs/MOLTO2-PROTOCOL.md).
