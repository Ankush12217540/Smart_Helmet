import network
import time
import ubinascii

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid="LPU Hostel 1", password="123454321", authmode=3)

print("Hotspot Active. Monitoring for devices...")

while True:
    # ap.status('stations') returns a list of connected devices
    connected_devices = ap.status('stations')
    
    print("\n--- Network Status ---")
    print(f"Total devices connected: {len(connected_devices)}")
    
    if len(connected_devices) > 0:
        for i, device in enumerate(connected_devices):
            # The MAC address comes as raw bytes, so we format it to look normal
            mac_address = ubinascii.hexlify(device[0], ':').decode('utf-8')
            print(f"Device {i+1} MAC: {mac_address}")
            
    time.sleep(5) # Check every 5 seconds