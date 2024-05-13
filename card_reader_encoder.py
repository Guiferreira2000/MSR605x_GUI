import os
import sys
import time

def send_command(device, command):
    """Send a command to the MSR device."""
    try:
        with open(device, 'wb') as dev:
            dev.write(command)
            dev.flush()
            print(f"Command sent: {command.hex()}")
    except Exception as e:
        print(f"Failed to send command: {e}", file=sys.stderr)

def read_response(device):
    """Read the response from the MSR device."""
    try:
        with open(device, 'rb') as dev:
            print("Waiting for response...")
            time.sleep(2)  # Adjust based on actual device speed
            response = dev.read(1024)
            if response:
                print("Received response:", response.hex())  # Print hex for clarity
            else:
                print("No response received or empty response.")
            return response
    except Exception as e:
        print(f"Failed to read response: {e}", file=sys.stderr)

device_path = '/dev/hidraw1'  # Confirm this is the correct device path

# Reset command to ensure the device is in initial state
reset_command = b'\x1B\x61'  # ESC a
send_command(device_path, reset_command)

time.sleep(2)  # Give some time for the device to reset

# Read command as per the manual: ESC r
read_command = b'\x1B\x72'  # ESC r
send_command(device_path, read_command)

# Reading the response from the device
response = read_response(device_path)
