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

### Recommended: a dedicated virtual environment

Using a project virtual environment avoids the most common setup problem: `pip`
and `python3` resolving to *different* Python interpreters (e.g. a Homebrew
`python3` and an Anaconda `pip`), so a package installed by `pip` is not visible
to `python3`. It also sidesteps the "externally-managed-environment" (PEP 668)
error that Homebrew/Debian Python raise for system-wide installs.

Create the environment once, then activate it whenever you use the tool:

    python3 -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install -r requirements.txt

    python molto2.py

While the environment is active, `python` and `pip` both refer to it, so there
is no interpreter mismatch. Run `deactivate` to leave it. The `.venv/` directory
is git-ignored.

### Without a virtual environment

If you prefer a global install, make sure you install for the **same**
interpreter you run. Using `python3 -m pip` guarantees this:

    python3 -m pip install -r requirements.txt
    python3 molto2.py

(You can also install the requirements one by one: `pip install pyscard` and
`pip install sm4`.)

**Troubleshooting `ModuleNotFoundError: No module named 'sm4'`** even though the
install "succeeded": your `pip` and `python3` are different interpreters. Check
with `which python3`, `python3 -V`, `pip -V` — if they disagree, install with
`python3 -m pip install -r requirements.txt`, or just use a virtual environment
as above.

PCSC installation and configuration
-----------------------------------
The script uses the PCSC service to communicate with the device, so a few components
need to be installed first:

    sudo apt-get install libusb-dev libusb++
    sudo apt-get install libccid
    sudo apt-get install pcscd
    sudo apt-get install libpcsclite1
    sudo apt-get install libpcsclite-dev
    sudo apt-get install pcsc-tools

PCSC ships with a predefined list of supported hardware, primarily smart card readers.
As the Molto2v2 is a relatively new product, it is not listed in the default
configuration, so it has to be added manually:

 - Open the device list file, usually located at the path below (the exact folder name
   may vary slightly):

       sudo nano /usr/lib/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist

   (if the file is not found, try `sudo find / -name Info.plist`).

 - Add `<string>0x349E</string>` at the end of the `<key>ifdVendorID</key>` section.
 - Add `<string>0x0300</string>` at the end of the `<key>ifdProductID</key>` section.
 - Add `<string>Token2 Molto2</string>` at the end of the `<key>ifdFriendlyName</key>` section.
 - Save the file and restart the system for the changes to take effect.

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

License
-------
This project is released under the MIT License. See [LICENSE.md](LICENSE.md) for details.

Developed by the Token2 R&D Team (https://www.token2.com/).

Protocol
--------
The device wire protocol (APDUs, SM4/MAC construction, TLV layouts) is
documented in [docs/PROTOCOL.md](docs/PROTOCOL.md).
