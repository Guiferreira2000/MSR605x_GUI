from msr605x import MSR605X
import time

ESC = b"\x1b"
FS = b"\x1c"

def wait_for_write_completion(msr, timeout=10):
    """Wait for the write operation to complete by checking device readiness."""
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        response = msr.recv_message(timeout=500)  # Poll every 0.5 seconds
        if response:
            status = response[1]
            return status
    return None  # Timeout if no response

def main():
    msr = MSR605X()
    msr.connect()
    msr.reset()
    print("MSR605X connected and ready.")

    # Prepare the data block
    data_block = (
        ESC + b's' +
        ESC + b'\x01' + b'FRNACISCO55' +
        ESC + b'\x02' + b'12345' +
        ESC + b'\x03' + b'99999999999' +
        b'?' + FS
    )

    # Send the write command
    msr.send_message(ESC + b'w' + data_block)
    print("Write command sent. Swipe the card...")

    # Wait for write completion based on device readiness
    status = wait_for_write_completion(msr)
    if status is not None:
        if status == 0x30:
            print("Write successful!")
        else:
            print(f"Write failed. Status code: {hex(status)}")
    else:
        print("Write operation timed out or no status response received.")

if __name__ == "__main__":
    main()
