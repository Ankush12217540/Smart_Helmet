import machine
import time
import math

print("--- MPU6050 Hardware Test ---")

# ==========================================
# 1. INITIALIZE I2C
# ==========================================
# ESP32 standard I2C pins: SDA=21, SCL=22
i2c = machine.SoftI2C(scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)

print("Scanning for I2C devices...")
devices = i2c.scan()

if len(devices) == 0:
    print("❌ ERROR: No I2C devices found!")
    print("Check your jumper wires. SDA must be on 21, SCL must be on 22.")
else:
    print("✅ I2C Devices found at addresses:", [hex(device) for device in devices])
    if 0x68 in devices or 0x69 in devices:
        print("✅ MPU6050 found! Starting data stream...\n")
    else:
        print("⚠️ Device found, but it doesn't match the standard MPU6050 address (0x68).")

# ==========================================
# 2. COMPACT MPU6050 DRIVER
# ==========================================
class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        # Wake up the MPU6050 (it starts in sleep mode)
        self.i2c.writeto_mem(self.addr, 0x6B, bytes([0])) 

    def get_force(self):
        try:
            # Read 6 bytes of accelerometer data
            data = self.i2c.readfrom_mem(self.addr, 0x3B, 6)
            
            # Combine high and low bytes
            x = (data[0] << 8 | data[1])
            y = (data[2] << 8 | data[3])
            z = (data[4] << 8 | data[5])
            
            # Convert to signed 16-bit integers
            x = x - 65536 if x > 32767 else x
            y = y - 65536 if y > 32767 else y
            z = z - 65536 if z > 32767 else z
            
            # Calculate total G-Force vector (1G = 16384 at default settings)
            return math.sqrt((x/16384)**2 + (y/16384)**2 + (z/16384)**2)
        except Exception as e:
            print(f"Read Error: {e}")
            return 0.0

# ==========================================
# 3. MAIN LOOP
# ==========================================
# Only try to read the sensor if it was actually found in the scan
if 0x68 in devices or 0x69 in devices:
    # Use 0x68 by default, or 0x69 if the AD0 pin is pulled high
    addr = 0x68 if 0x68 in devices else 0x69
    mpu = MPU6050(i2c, addr)
    
    while True:
        try:
            force = mpu.get_force()
            print(f"Total G-Force: {force:.2f} G")
            
            # If you shake it hard, trigger a mock "Crash"
            if force > 2.5:
                print("💥 IMPACT DETECTED! 💥")
                
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            print("\nTest Stopped.")
            break