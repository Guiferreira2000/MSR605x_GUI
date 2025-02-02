from msr605x import MSR605X

def parse_track_data(data):
    """Parse the raw card data into individual tracks."""
    tracks = {
        "Track 1": "",
        "Track 2": "",
        "Track 3": ""
    }

    # Parse Track 1
    track1_start = data.find('%')
    track1_end = data.find('?', track1_start)
    if track1_start != -1 and track1_end != -1:
        tracks["Track 1"] = data[track1_start:track1_end + 1]

    # Parse Track 2
    track2_start = data.find(';')
    track2_end = data.find('?', track2_start)
    if track2_start != -1 and track2_end != -1:
        tracks["Track 2"] = data[track2_start:track2_end + 1]

    # Parse Track 3
    # Look for potential starting characters
    for track3_char in ['+', '=', ';']:
        track3_start = data.find(track3_char, track2_end + 1)  # Start after Track 2
        track3_end = data.find('?', track3_start)
        if track3_start != -1 and track3_end != -1:
            tracks["Track 3"] = data[track3_start:track3_end + 1]
            break  # Stop after finding the first valid Track 3

    return tracks

def main():
    # Initialize and connect to the MSR605X
    msr = MSR605X()
    msr.connect()
    msr.reset()

    print("MSR605X connected and ready.")

    # Loop until data is read
    while True:
        # Send the read command for all tracks
        print("Sending read command for all tracks...")
        msr.send_message(b"\x1b" + b"r")  # ESC + "r" to read all tracks

        # Wait for a response with a longer timeout (e.g., 10 seconds)
        print("Swipe a card to read data...")
        response = msr.recv_message(timeout=10000)  # 10 seconds timeout

        if response:
            data = response.decode('ascii')
            print("\nRaw Card Data:", data)

            # Parse the track data
            tracks = parse_track_data(data)

            # Print the parsed track data
            for track_name, track_data in tracks.items():
                if track_data:
                    print(f"{track_name}: {track_data}")
                else:
                    print(f"{track_name}: No data")

            break  # Exit the loop after reading data
        else:
            print("No data read from the card. Please try again.\n")

if __name__ == "__main__":
    main()