"""Throwaway spike: can python-xlib grab the pen and decode position + pressure?

Run: uv run python spikes/xi2_grab.py [seconds]
Grabs the pen for a few seconds (default 2), prints what it sees, releases it.
"""
import select
import struct
import sys
import time

from Xlib import X, display
from Xlib.ext import ge, xinput

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0

d = display.Display()
root = d.screen().root
print("XI version", d.xinput_query_version().major_version, d.xinput_query_version().minor_version)

pen = None
for dev in d.xinput_query_device(xinput.AllDevices).devices:
    has_pressure = False
    for c in dev.classes:
        if c.type == xinput.ValuatorClass:
            label = d.get_atom_name(c.label) if c.label else ""
            if label == "Abs Pressure":
                has_pressure = True
    if has_pressure and dev.use == xinput.SlavePointer:
        pen = dev
        print("pen:", dev.deviceid, dev.name, "attached to", dev.attachment)
        for c in dev.classes:
            if c.type == xinput.ValuatorClass:
                print("  valuator", c.number, d.get_atom_name(c.label), c.min, c.max)
            elif c.type == xinput.ButtonClass:
                print("  buttons", len(c.state))
if pen is None:
    sys.exit("no pen found")

# Keep event payloads as raw bytes: python-xlib's struct drops the valuators.
opcode = d.query_extension(xinput.extname).major_opcode
for ev in (xinput.ButtonPress, xinput.ButtonRelease, xinput.Motion):
    d.display.ge_event_data.pop((opcode, ev), None)

mask = xinput.ButtonPressMask | xinput.ButtonReleaseMask | xinput.MotionMask
reply = root.xinput_grab_device(
    pen.deviceid, X.CurrentTime, xinput.GrabModeAsync, xinput.GrabModeAsync, False, mask
)
print("grab status (0 = success):", reply.status)
d.sync()


def decode(data):
    deviceid, t, detail = struct.unpack_from("=HII", data, 0)
    root_x, root_y = struct.unpack_from("=ii", data, 22)
    blen, vlen = struct.unpack_from("=HH", data, 38)
    off = 70 + blen * 4
    vmask = int.from_bytes(data[off:off + vlen * 4], "little")
    off += vlen * 4
    vals = {}
    for i in range(vlen * 32):
        if vmask >> i & 1:
            integral, frac = struct.unpack_from("=iI", data, off)
            vals[i] = integral + frac / 2**32
            off += 8
    return deviceid, detail, root_x / 65536, root_y / 65536, vals


end = time.time() + SECONDS
n = 0
while time.time() < end:
    if not d.pending_events():
        select.select([d.fileno()], [], [], 0.1)
        continue
    e = d.next_event()
    if e.type == ge.GenericEventCode and e.extension == opcode:
        n += 1
        if n <= 15 or e.evtype != xinput.Motion:
            print(e.evtype, decode(e.data))
print("events seen:", n)
d.xinput_ungrab_device(pen.deviceid, X.CurrentTime)
d.sync()
print("released")
