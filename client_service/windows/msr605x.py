#!/usr/bin/env python3
"""
WIP library for the MSR605X

This file contains:
  - The MSR605X class with low-level and high-level functions.
  - Utility functions for BPC/BPI setup, parsing track data, write completion,
    writing card data, and erasing card data.
  - A main() function using subparsers:
      * "read" mode: reads card data.
      * "write" mode: writes card data with track data passed as command-line arguments.
      * "erase" mode: erases card data for specified tracks.
"""

import usb.core
import usb.util
import usb.backend.libusb1  # Explicitly import the libusb1 backend
import time
import argparse

ESC = b"\x1b"
FS  = b"\x1c"

SEQUENCE_START_BIT   = 0b10000000
SEQUENCE_END_BIT     = 0b01000000
SEQUENCE_LENGTH_BITS = 0b00111111

class MSR605X:
    """Represents an MSR605X device."""
    def __init__(self, **kwargs):
        if "idVendor" not in kwargs:
            kwargs["idVendor"] = 0x0801
            kwargs["idProduct"] = 0x0003
        # Force pyusb to use the libusb1 backend
        backend = usb.backend.libusb1.get_backend()
        self.dev = usb.core.find(backend=backend, **kwargs)
        if self.dev is None:
            raise ValueError("Device not found. Check connection and driver installation.")
        self.hid_endpoint = None

    def connect(self):
        """Establish a connection to the MSR605X with retry on 'Resource busy' errors."""
        max_attempts = 3
        attempts = 0
        while attempts < max_attempts:
            try:
                try:
                    if self.dev.is_kernel_driver_active(0):
                        self.dev.detach_kernel_driver(0)
                except NotImplementedError:
                    # Not supported on Windows; ignore.
                    pass
                self.dev.set_configuration()
                break
            except usb.core.USBError as e:
                if hasattr(e, 'errno') and e.errno == 16:  # Resource busy
                    attempts += 1
                    time.sleep(1)
                    usb.util.dispose_resources(self.dev)
                else:
                    raise e
        if attempts == max_attempts:
            raise usb.core.USBError("Unable to set configuration after several attempts: Resource busy")
        config = self.dev.get_active_configuration()
        interface = config[(0, 0)]
        self.hid_endpoint = interface.endpoints()[0]

    def _make_header(self, start_of_sequence: bool, end_of_sequence: bool, length: int):
        if length < 0 or length > 63:
            raise ValueError("Length must be between 0 and 63")
        header = length
        if start_of_sequence:
            header |= SEQUENCE_START_BIT
        if end_of_sequence:
            header |= SEQUENCE_END_BIT
        return bytes([header])

    def _encapsulate_message(self, message):
        idx = 0
        while idx < len(message):
            payload = message[idx:idx+63]
            header = self._make_header(idx == 0, len(message) - idx < 64, len(payload))
            padding = b"\0" * (63 - len(payload))
            yield header + payload + padding
            idx += 63

    def _send_packet(self, packet):
        self.dev.ctrl_transfer(0x21, 9, wValue=0x0300, wIndex=0, data_or_wLength=packet)

    def _recv_packet(self, timeout=0):
        try:
            return bytes(self.hid_endpoint.read(64, timeout=timeout))
        except usb.core.USBError as error:
            if hasattr(error, 'errno'):
                if error.errno == 110:  # Timeout
                    return None
                elif error.errno == 75:  # Overflow error: ignore and return None
                    return None
            raise error

    def send_message(self, message):
        """Send a message to the MSR605X."""
        for packet in self._encapsulate_message(message):
            self._send_packet(packet)

    def recv_message(self, timeout=0):
        """Receive a message from the MSR605X."""
        message = b""
        while True:
            packet = self._recv_packet(timeout=timeout)
            if packet is None:
                return None  # No data received
            payload_length = packet[0] & SEQUENCE_LENGTH_BITS
            payload = packet[1:1 + payload_length]
            message += payload
            if packet[0] & SEQUENCE_END_BIT:
                break
        return message

    def reset(self):
        """Send a reset command to the MSR605X."""
        self.send_message(ESC + b"a")

    def get_firmware_version(self):
        """Retrieve the firmware version."""
        self.send_message(ESC + b"v")
        ret = self.recv_message()
        if ret and ret.startswith(ESC):
            return ret[1:]
        return None

    def check_card_present(self):
        """Check for card presence using a sensor test command."""
        self.send_message(ESC + b"\x86")
        response = self.recv_message(timeout=5000)
        if response and response.startswith(ESC + b"\x30"):
            return True
        return False

    def read_tracks(self):
        """Read data from all tracks."""
        self.send_message(ESC + b"r")
        response = self.recv_message(timeout=5000)
        if response and response.startswith(ESC):
            return response
        return None

# Helper function to release the device.
def finalize_device(msr):
    usb.util.dispose_resources(msr.dev)

# Utility functions

def set_bpc_bpi(msr, mode="read"):
    """
    Set the BPC and BPI for better swipe detection.
    mode: 'read' for 75 BPI or 'write' for 210 BPI.
    """
    msr.send_message(ESC + b'o' + bytes([0x07, 0x05, 0x05]))
    bpc_ack = msr.recv_message(timeout=2000)
    print(f"BPC Set ACK: {bpc_ack.hex() if bpc_ack else 'No response'}")
    if mode == "read":
        msr.send_message(ESC + b'b' + b'\xA0')  # Track 1 - 75 BPI
        print(f"Track 1 BPI ACK: {msr.recv_message(timeout=2000)}")
        msr.send_message(ESC + b'b' + b'\x4B')  # Track 2 - 75 BPI
        print(f"Track 2 BPI ACK: {msr.recv_message(timeout=2000)}")
        msr.send_message(ESC + b'b' + b'\xC0')  # Track 3 - 75 BPI
        print(f"Track 3 BPI ACK: {msr.recv_message(timeout=2000)}")
        # Reset to apply settings.
        msr.send_message(ESC + b'a')
        time.sleep(0.5)
    elif mode == "write":
        msr.send_message(ESC + b'b' + b'\xA1')  # Track 1 - 210 BPI
        print(f"Track 1 BPI ACK: {msr.recv_message(timeout=2000)}")
        msr.send_message(ESC + b'b' + b'\xD2')  # Track 2 - 210 BPI
        print(f"Track 2 BPI ACK: {msr.recv_message(timeout=2000)}")
        msr.send_message(ESC + b'b' + b'\xC1')  # Track 3 - 210 BPI
        print(f"Track 3 BPI ACK: {msr.recv_message(timeout=2000)}")
    else:
        raise ValueError("Mode must be 'read' or 'write'")

def set_coercivity(msr, mode="hi"):
    """
    Set the coercivity of the card.
    mode: 'hi' for Hi-Co (ESC + x) or 'low' for Low-Co (ESC + y)
    """
    if mode.lower() == "hi":
        msr.send_message(ESC + b'x')
        resp = msr.recv_message(timeout=2000)
        if resp != ESC + b'0':
            print("Failed to set Hi-Co")
        else:
            print("Coercivity set to Hi-Co")
    elif mode.lower() == "low":
        msr.send_message(ESC + b'y')
        resp = msr.recv_message(timeout=2000)
        if resp != ESC + b'0':
            print("Failed to set Low-Co")
        else:
            print("Coercivity set to Low-Co")
    else:
        raise ValueError("Invalid coercivity mode. Choose 'hi' or 'low'.")

def get_coercivity_status(msr):
    """
    Retrieve the current coercivity status.
    Sends <ESC> d and checks if the response indicates Hi-Co (H) or Low-Co (L).
    """
    msr.send_message(ESC + b'd')
    resp = msr.recv_message(timeout=2000)
    if resp and len(resp) >= 2:
        if resp[1:2] == b'H':
            return "hi"
        elif resp[1:2] == b'L':
            return "low"
    return "unknown"

def erase_card(msr, select_byte):
    """
    Erase card data using the erase command.
    [Select Byte] is a byte specifying which tracks to erase:
      0x00: Track 1 only
      0x02: Track 2 only
      0x04: Track 3 only
      0x03: Track 1 & 2
      0x05: Track 1 & 3
      0x06: Track 2 & 3
      0x07: Track 1, 2 & 3
    """
    msr.send_message(ESC + b'c' + bytes([select_byte]))
    resp = msr.recv_message(timeout=2000)
    if resp == ESC + b'0':
        print("Erase successful!")
    elif resp == ESC + b'A':
        print("Erase failed!")
    else:
        print("Unexpected response:", resp)

def parse_tracks_arg(tracks_str):
    """
    Parse a string representing tracks to erase into the corresponding select byte.
    Acceptable values:
      "1" or "track1"   => 0x00
      "2" or "track2"   => 0x02
      "3" or "track3"   => 0x04
      "1,2"             => 0x03
      "1,3"             => 0x05
      "2,3"             => 0x06
      "1,2,3" or "all"  => 0x07
    """
    mapping = {
        "1": 0x00,
        "track1": 0x00,
        "2": 0x02,
        "track2": 0x02,
        "3": 0x04,
        "track3": 0x04,
        "1,2": 0x03,
        "1,3": 0x05,
        "2,3": 0x06,
        "1,2,3": 0x07,
        "all": 0x07,
    }
    key = tracks_str.replace(" ", "").lower()
    return mapping.get(key)

def parse_track_data(data):
    """Parse raw card data into individual tracks."""
    tracks = {"Track 1": "", "Track 2": "", "Track 3": ""}

    # Parse Track 1 (starts with '%')
    track1_start = data.find('%')
    track1_end = data.find('?', track1_start)
    if track1_start != -1 and track1_end != -1:
        tracks["Track 1"] = data[track1_start:track1_end + 1]

    # Parse Track 2 (starts with ';')
    track2_start = data.find(';')
    track2_end = data.find('?', track2_start)
    if track2_start != -1 and track2_end != -1:
        tracks["Track 2"] = data[track2_start:track2_end + 1]

    # Parse Track 3 (try '+', '=', or ';' after Track 2)
    for char in ['+', '=', ';']:
        track3_start = data.find(char, track2_end + 1)
        if track3_start != -1:
            track3_end = data.find('?', track3_start)
            if track3_end != -1:
                tracks["Track 3"] = data[track3_start:track3_end + 1]
                break
    return tracks

def parse_and_clean_tracks(raw_data):
    """
    1) Parse raw card data into track strings.
    2) Remove leading/trailing sentinels (% or ; at start, ? at end).
    3) Return a dict with cleaned track values.
    """
    raw_tracks = parse_track_data(raw_data)
    cleaned = {}
    for track_name, track_value in raw_tracks.items():
        track_value = track_value.strip()  # remove whitespace
        # Remove leading '%' or ';'
        if track_value.startswith('%') or track_value.startswith(';'):
            track_value = track_value[1:]
        # Remove trailing '?' if present
        if track_value.endswith('?'):
            track_value = track_value[:-1]
        cleaned[track_name] = track_value
    return cleaned

def wait_for_write_completion(msr, timeout=10):
    """Wait for the write operation to complete by polling for a status."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = msr.recv_message(timeout=500)
        if response and len(response) > 1:
            status = response[1]
            return status
        time.sleep(0.1)
    return None

def write_card(msr, track1, track2, track3):
    """Write card data using the specified track data."""
    data_block = (
        ESC + b's' +
        ESC + b'\x01' + track1 +
        ESC + b'\x02' + track2 +
        ESC + b'\x03' + track3 +
        b'?' + FS
    )
    msr.send_message(ESC + b'w' + data_block)
    print("Write command sent. Swipe the card...", flush=True)
    status = wait_for_write_completion(msr)
    if status is not None:
        if status == 0x30:
            print("Write successful!")
        else:
            print(f"Write failed. Status code: {hex(status)}")
    else:
        print("Write operation timed out or no status response received.")

def read_card_data():
    """
    High-level function for reading and returning cleaned track data.
    Returns a dict: {"Track 1": <cleaned>, "Track 2": <cleaned>, "Track 3": <cleaned>}
    """
    msr = MSR605X()
    msr.connect()
    msr.reset()
    print("MSR605X connected and ready.")
    set_bpc_bpi(msr, mode="read")
    print("Sending read command for all tracks...")
    msr.send_message(ESC + b"r")
    print("Swipe a card to read data...")
    response = msr.recv_message(timeout=10000)
    if response:
        raw_data = response.decode('ascii', errors='ignore')
        print("\nRaw Card Data:", raw_data)
        cleaned_tracks = parse_and_clean_tracks(raw_data)
    else:
        cleaned_tracks = {"Track 1": "", "Track 2": "", "Track 3": ""}
    # Release the device resources so it’s not left busy
    finalize_device(msr)
    return cleaned_tracks

def main():
    parser = argparse.ArgumentParser(description="MSR605X read/write/erase utility")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # Read sub-command (no extra args)
    subparsers.add_parser("read", help="Read card data")

    # Write sub-command requires track data.
    write_parser = subparsers.add_parser("write", help="Write card data")
    write_parser.add_argument("--track1", required=True, help="Data for Track 1")
    write_parser.add_argument("--track2", required=True, help="Data for Track 2")
    write_parser.add_argument("--track3", required=True, help="Data for Track 3")
    write_parser.add_argument("--coercivity", choices=["hi", "low"], default="hi", help="Coercivity mode to use (hi or low)")

    # Erase sub-command requires tracks specification.
    erase_parser = subparsers.add_parser("erase", help="Erase card data")
    erase_parser.add_argument("--tracks", default="all", help="Tracks to erase (e.g., '1', '2', '3', '1,2', '1,3', '2,3', 'all')")

    args = parser.parse_args()

    msr = MSR605X()
    msr.connect()
    msr.reset()
    print("MSR605X connected and ready.")

    if args.mode == "read":
        set_bpc_bpi(msr, mode="read")
        print("Sending read command for all tracks...")
        msr.send_message(ESC + b"r")
        print("Swipe a card to read data...")
        response = msr.recv_message(timeout=10000)
        if response:
            data = response.decode('ascii', errors='ignore')
            print("\nRaw Card Data:", data)
            tracks = parse_track_data(data)
            for track_name, track_data in tracks.items():
                if track_data:
                    print(f"{track_name}: {track_data}")
                else:
                    print(f"{track_name}: No data")
        else:
            print("No data read from the card. Please try again.")
    elif args.mode == "write":
        set_bpc_bpi(msr, mode="write")
        set_coercivity(msr, mode=args.coercivity)
        current_coercivity = get_coercivity_status(msr)
        print(f"Current coercivity status: {current_coercivity}")
        # Convert track data to bytes.
        track1_data = args.track1.encode()
        track2_data = args.track2.encode()
        track3_data = args.track3.encode()
        write_card(msr, track1_data, track2_data, track3_data)
    elif args.mode == "erase":
        set_bpc_bpi(msr, mode="write")
        sel_byte = parse_tracks_arg(args.tracks)
        if sel_byte is None:
            print("Invalid tracks specification.")
        else:
            print(f"Erasing tracks with select byte: {hex(sel_byte)}")
            erase_card(msr, sel_byte)

if __name__ == "__main__":
    main()
