""" WIP library for the MSR605X """

import usb
import usb.core

SEQUENCE_START_BIT = 0b10000000
SEQUENCE_END_BIT = 0b01000000
SEQUENCE_LENGTH_BITS = 0b00111111
ESC = b"\x1b"

class MSR605X:
    """ Represents a MSR605X device

    There are three levels of abstraction that this class can be used at:
    - raw 64 byte hid packets: _send_packet and _recv_packet
    - plain MSR605 serial protocol messages: send_message and recv_message
    - higher level functions: reset, ... (more to be added)

    """
    def __init__(self, **kwargs):
        if "idVendor" not in kwargs:
            kwargs["idVendor"] = 0x0801
            kwargs["idProduct"] = 0x0003
        self.dev = usb.core.find(**kwargs)
        self.hid_endpoint = None

    def connect(self):
        """ Establish a connection to the MSR605X """
        try:
            dev = self.dev
            if dev is None:
                raise ValueError("Device not found. Please check the connection and try again.")
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
            dev.set_configuration()
            config = dev.get_active_configuration()
            interface = config.interfaces()[0]
            self.hid_endpoint = interface.endpoints()[0]
        except usb.core.USBError as e:
            raise ConnectionError(f"Failed to connect to the device: {e}")

    def _make_header(self, start_of_sequence: bool, end_of_sequence: bool, length: int):
        if length < 0 or length > 63:
            raise ValueError("Length must be a non-negative number no more than 63")
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

    def _recv_packet(self, **kwargs):
        try:
            return bytes(self.hid_endpoint.read(64, **kwargs))
        except usb.core.USBError as error:
            if error.errno == 110:
                return None
            raise error

    def send_message(self, message):
        """ Send a message to the MSR605X """
        for packet in self._encapsulate_message(message):
            self._send_packet(packet)

    def recv_message(self, timeout=1000):
        """ Receive message from the MSR605X """
        message = b""
        while True:
            try:
                packet = self._recv_packet(timeout=timeout)
                if packet is None and not message:
                    return None
                payload_length = packet[0] & SEQUENCE_LENGTH_BITS
                payload = packet[1:1+payload_length]
                message = message + payload
                if packet[0] & SEQUENCE_END_BIT:
                    break
            except usb.core.USBError as error:
                if error.errno == 110:  # Timeout error
                    print("Timeout occurred while receiving message.")
                    return None
                else:
                    raise error
        return message

    def reset(self):
        """ Sends reset message to the MSR605X """
        self.send_message(ESC + b"a")

    def get_firmware_version(self):
        """ Get the firmware version of the connected MSR605X """
        self.send_message(ESC + b"v")
        ret = self.recv_message()
        assert ret[0:1] == ESC
        return ret[1:]

    def read_track(self):
        """ Read track data from the MSR605X device """
        self.send_message(ESC + b"r")
        ret = self.recv_message()
        assert ret[0:1] == ESC
        return ret[1:]

    def write_track(self, track_number, data):
        """ Write data to the specified track """
        if not (1 <= track_number <= 3):
            raise ValueError("Track number must be between 1 and 3")

        if isinstance(data, str):
            data = data.encode('utf-8')

        command = (ESC + b'w' + ESC + b's' + ESC +
                bytes(f"[0{track_number}]", 'utf-8') +
                data + b'?' + ESC + b'\x1c')

        self.send_message(command)

        feedback = self.recv_message()
        if feedback and (b'\x1b0' in feedback or b'\x1b1' in feedback):
            print(f"Successfully wrote to track {track_number}.")
        else:
            error_message = f"Failed to write data to track {track_number}. Device response: {feedback}"
            raise Exception(error_message)