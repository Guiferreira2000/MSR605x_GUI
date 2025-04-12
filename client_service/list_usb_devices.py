
import usb.core
import usb.util

def list_usb_devices():
    devices = usb.core.find(find_all=True)
    if devices is None:
        print("No USB devices found.")
        return

    print("List of USB devices:")
    for dev in devices:
        try:
            vendor_id = hex(dev.idVendor)
            product_id = hex(dev.idProduct)
            product = "N/A"
            if dev.iProduct:
                try:
                    product = usb.util.get_string(dev, dev.iProduct)
                except Exception:
                    product = "N/A"
            print(f"Vendor: {vendor_id}, Product: {product_id}, Description: {product}")
        except usb.core.USBError as e:
            print(f"Error reading device info: {e}")
        except Exception as err:
            print(f"Unexpected error: {err}")

if __name__ == "__main__":
    list_usb_devices()
