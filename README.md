# WIP MSR605X Magstripe Reader/Writer Library

This is an in-progress library for the MSR605X magstripe reader/writer. The MSR605X appears as a USB HID device and uses a protocol that appears to be a small wrapper around the older serial protocol used by other MSR devices.

# Protocol Details

The MSR605X uses 64-byte USB HID packets to encapsulate what appears to be the MSR605's serial protocol. The MSR605's serial protocol is documented in section 6 of the [MSR605 Programmer's Manual](https://usermanual.wiki/Pdf/MSR60520Programmers20Manual.325315846/help).

Messages to be sent over USB are split into chunks with a maximum size of 63 bytes. A 64-byte USB HID packet is then constructed from a 1-byte header, a chunk of the message, and sometimes some extra bytes to make the packet exactly 64 bytes regardless of the size of the chunk. The 1-byte header consists of:

- A single bit indicating if this packet is the first in the sequence.
- A single bit indicating if this packet is the last in the sequence.
- A 6-bit unsigned integer representing the length of the payload in the current packet.

For example, a header byte of `0b11000010` (`0xC2`) indicates:

- Start of sequence bit (`0b10000000`) is set.
- End of sequence bit (`0b01000000`) is set.
- Payload length is `0b00000010` (2).

# Encapsulation Examples

## Single Packet Example

**Message:** `"string"`

**Packet 1:**
```
0xC6737472696E67000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
```

**Packet 1 Header:** `0b11000110` (`0xC6`):
- Start of sequence
- End of sequence
- Payload length = 6 (`0b000110`)

**Payload:** `0x737472696E67` ("string")

## Multiple Packet Example

**Message:** A long sequence of 'A' characters exceeding 63 bytes.

**Packet 1:**
```
0xBF414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141
```
- **Header:** `0b10111111` (`0xBF`): Start of sequence, payload length = 63 (`0b00111111`).

**Packet 2:**
```
0x3F414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141
```
- **Header:** `0b00111111` (`0x3F`): Payload length = 63.

**Packet 3:**
```
0x4F414141414141414141414141414141000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
```
- **Header:** `0b01001111` (`0x4F`): End of sequence, payload length = 15 (`0b001111`).

# Read and Write Operations

## Writing Data to the MSR605X

To write data, the following sequence is used:

1. **Start Command:** `ESC + 'w'` (`0x1B 0x77`) initiates the write process.
2. **Data Block Start:** `ESC + 's'` (`0x1B 0x73`) signals the start of data transmission.
3. **Track Data:**
   - Track 1: `ESC + 0x01 + "ABC123"`
   - Track 2: `ESC + 0x02 + "12345"`
   - Track 3: `ESC + 0x03 + "67890"`
4. **End of Data:** `? + FS` (`0x3F 0x1C`) marks the end of data.
5. **Status Acknowledgment:** Wait for `ESC + [status]`, where `0x30` means success.

**Example:**
```
ESC + 'w' + ESC + 's' + ESC + 0x01 + 'ABC123' + ESC + 0x02 + '12345' + ESC + 0x03 + '67890' + '?' + FS
```

## Reading Data from the MSR605X

1. **Read Command:** `ESC + 'r'` (`0x1B 0x72`) to initiate reading all tracks.
2. **Data Response:** Device responds with the raw track data:
   - Track 1 starts with `%`
   - Track 2 starts with `;`
   - Track 3 may start with `;`, `+`, or `=` depending on the card.
3. **End of Data:** Ends with `FS + ESC + 0x30`.

**Example:**
```
ESC + 'r'  # Send read command
Response: ESC + 's' + ESC + 0x01 + '%ABC123?' + ESC + 0x02 + ';12345?' + ESC + 0x03 + ';67890??' + FS + ESC + 0x30
```

# Requirements

- Python 3
- `pyusb` library (`pip install pyusb`)
- Suitable USB backend for `pyusb` (refer to the [pyusb tutorial](https://github.com/pyusb/pyusb/blob/master/docs/tutorial.rst))

# Debugging Setup

- MSR605X physically attached to Linux host
  - Passed through to Windows VM (optional)
- `usbmon` kernel module on Linux intercepts USB packets
  - Wireshark records intercepted USB packets
- Windows VM with MSR605X GUI

# Documentation

Based on the works of [msr605x](https://github.com/rubicae/msr605x/blob/master/msr605x.py) and the [MSR605 Programmer's Manual](https://usermanual.wiki/Pdf/MSR60520Programmers20Manual.325315846/help).