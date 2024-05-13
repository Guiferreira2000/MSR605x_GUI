from msr605x import MSR605X

def parse_tracks(data):
    # Initialize empty track data
    tracks = {'Track 1': '', 'Track 2': '', 'Track 3': ''}
    # Each track's data is split by escape sequences followed by a control byte
    try:
        # Split the data into potential track segments
        segments = data.split(b'\x1b')[1:]  # Skip the first segment as it might be non-track data or firmware version
        for seg in segments:
            if seg[1:2] == b'%':  # Track 1 data starts after %, ends with ?
                end_idx = seg.find(b'?') + 1
                tracks['Track 1'] = seg[1:end_idx].decode('utf-8')
            elif seg[1:2] == b';':  # Track 2 and 3 data starts after ;, ends with ?
                end_idx = seg.find(b'?') + 1
                if seg[0:1] == b'\x02':  # Distinguish based on prefix (adjust this based on your actual data structure)
                    tracks['Track 2'] = seg[1:end_idx].decode('utf-8')
                elif seg[0:1] == b'\x03':
                    tracks['Track 3'] = seg[1:end_idx].decode('utf-8')
    except Exception as e:
        print(f"Error parsing tracks: {e}")

    return tracks

def main():
    msr = MSR605X()

    try:
        msr.connect()
        print("Connected to MSR605X")
        firmware_version = msr.get_firmware_version()
        print("Firmware Version:", firmware_version.decode('utf-8'))

        while True:
            print("Please swipe the card...")
            track_data = msr.read_track()
            if track_data:
                print("Raw Track Data:", track_data)
                tracks = parse_tracks(track_data)
                for track, content in tracks.items():
                    print(f"{track}: {content if content else 'No data read'}")
                # track1_data = "TESTE02"
                # msr.write_track(1, track1_data.encode('utf-8'))
            else:
                print("No data read from the card. Please swipe again.")

    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Exiting...")
    except Exception as e:
        print("An error occurred:", e)

if __name__ == "__main__":
    main()
