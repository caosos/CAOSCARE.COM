"""Infrared code tables for TVs (and later ACs) reached through an IR blaster.

Data, one source: a device names its table (`SmartDevice.ir_codeset`); the IR adapter
(device_ir_adapter.py) only ever looks codes up here. Add a brand by adding a table and
recording where its codes came from and how they were proven.
"""

CODESETS = {
    # Sony Bravia, SIRC 12-bit (address 1). Values are ESPHome's decoded `data` (the IR Mate's
    # receiver reported its own power send as data=0x0A90). Source: Flipper-IRDB TVs/Sony
    # (Lucaslhm/Flipper-IRDB), Sony_Bravia.ir + Power_off; power_on is Sony's discrete code 46.
    # Proven on the Room 214 Bravia 2026-10-12: power on/off/on, volume 100 down + 50 up.
    "sony_sirc12": {
        "transmit": "send_sony",          # esphome action suffix on the blaster (`<endpoint>_send_sony`)
        "nbits": 12,
        "codes": {
            "power_on": 0x750, "power_off": 0xF50, "power_toggle": 0xA90,
            "volume_up": 0x490, "volume_down": 0xC90, "mute": 0x290, "input": 0xA50,
        },
        "volume_steps": 100,              # a press moves 1 of 0-100
        "step_gap_s": 0.35,
    },
}


def codeset(name: str) -> dict:
    if name not in CODESETS:
        raise RuntimeError(f"no infrared code table named {name!r}")
    return CODESETS[name]
