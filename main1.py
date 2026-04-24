import machine
import time
import dht
import math
import network
import socket
import urequests
import ubinascii

print("Booting Smart Helmet OS (God Mode)...")

# ==========================================
# 1. CREDENTIALS & CONFIGURATION
# ==========================================
WIFI_SSID = "Ankush"
WIFI_PASS = "123456789"

PICO_IP = "192.168.43.15" 
PICO_PORT = 5005

# Twilio Credentials
TWILIO_SID = "ACb80c6b5e5f56903e2d908a04e6a62126"
TWILIO_AUTH = "e72a0085ac7958fd730734961feec236"
TWILIO_PHONE = "+12605085662"
MY_PHONE = "+919122476011"

# Telegram Credentials
TELEGRAM_BOT_TOKEN = "8368370250:AAHQv0dB0zLxl9BravhuGio4mHD1dZni2a0"
TELEGRAM_CHAT_ID = "5815757406"

# Thresholds & Locations
ALCOHOL_THRESHOLD = 1500
RESERVE_GPS = "31.251503,75.704496"

# ==========================================
# 2. PIN CONFIGURATIONS
# ==========================================
mq3_sensor = machine.ADC(machine.Pin(34))
mq3_sensor.atten(machine.ADC.ATTN_11DB) 

pir_sensor = machine.Pin(25, machine.Pin.IN)
ir_sensor = machine.Pin(26, machine.Pin.IN)
vib_sensor = machine.Pin(27, machine.Pin.IN)
sos_switch = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
dht_sensor = dht.DHT11(machine.Pin(4))

buzzer = machine.Pin(14, machine.Pin.OUT)
internal_led = machine.Pin(2, machine.Pin.OUT) 

gps_uart = machine.UART(2, baudrate=9600, rx=16, tx=17)
i2c = machine.SoftI2C(scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)

# ==========================================
# 3. DRIVERS & UTILITIES
# ==========================================
class SimpleI2CLCD:
    def __init__(self, i2c, addr):
        self.i2c, self.addr, self.backlight = i2c, addr, 0x08
        time.sleep_ms(50)
        for cmd in [0x33, 0x32, 0x28, 0x0C, 0x06, 0x01]:
            self.send(cmd, 0)
        time.sleep_ms(2)
    def send(self, val, mode):
        high, low = val & 0xF0, (val << 4) & 0xF0
        for half in [high, low]:
            self.i2c.writeto(self.addr, bytes([half | mode | self.backlight | 0x04]))
            self.i2c.writeto(self.addr, bytes([half | mode | self.backlight & ~0x04]))
    def move_to(self, x, y):
        self.send(0x80 | (x + [0x00, 0x40, 0x14, 0x54][y]), 0)
    def putstr(self, text):
        for char in text: self.send(ord(char), 1)

class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c, self.addr = i2c, addr
        self.i2c.writeto_mem(self.addr, 0x6B, bytes([0])) 
    def get_force(self):
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x3B, 6)
            x, y, z = (data[0]<<8|data[1]), (data[2]<<8|data[3]), (data[4]<<8|data[5])
            x, y, z = (x-65536 if x>32767 else x), (y-65536 if y>32767 else y), (z-65536 if z>32767 else z)
            return math.sqrt((x/16384)**2 + (y/16384)**2 + (z/16384)**2)
        except:
            return 0.0

def pad(text):
    return str(text)[:20] + (" " * (20 - len(str(text))))

def convert_nmea_to_decimal(raw_val):
    """Converts raw NMEA (ddmm.mmmm) to decimal degrees for Google Maps."""
    try:
        dot_idx = raw_val.find('.')
        if dot_idx > 2:
            deg = float(raw_val[:dot_idx-2])
            mins = float(raw_val[dot_idx-2:])
            return str(deg + (mins/60))
    except:
        pass
    return None

def get_maps_link():
    """Returns a short Google Maps link. Uses reserve if GPS has no lock."""
    if gps_uart.any():
        try:
            line = gps_uart.readline().decode('utf-8').strip()
            if line.startswith('$GPRMC') and ',A,' in line:
                parts = line.split(',')
                lat = convert_nmea_to_decimal(parts[3])
                lon = convert_nmea_to_decimal(parts[5])
                if lat and lon:
                    return f"https://maps.google.com/?q={lat},{lon}"
        except:
            pass
    return f"https://maps.google.com/?q={RESERVE_GPS}"

# --- API ALERTS ---
def get_twilio_headers():
    auth_str = f"{TWILIO_SID}:{TWILIO_AUTH}"
    auth_b64 = ubinascii.b2a_base64(auth_str.encode('utf-8')).strip().decode('utf-8')
    return {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"}

def send_twilio_sms(message):
    print("📲 Sending Twilio SMS...")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    data = f"To={MY_PHONE}&From={TWILIO_PHONE}&Body={message}"
    try:
        res = urequests.post(url, data=data, headers=get_twilio_headers())
        res.close()
        print("✅ SMS Sent!")
    except Exception as e:
        print("❌ SMS Error:", e)

def call_twilio():
    print("📞 Initiating Twilio Voice Call...")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Calls.json"
    twiml_encoded = "%3CResponse%3E%3CSay%3EEmergency%20Alert.%20Please%20check%20messages.%3C%2FSay%3E%3C%2FResponse%3E"
    data = f"To={MY_PHONE}&From={TWILIO_PHONE}&Twiml={twiml_encoded}"
    try:
        res = urequests.post(url, data=data, headers=get_twilio_headers())
        res.close()
        print("✅ Voice Call Initiated!")
    except Exception as e:
        print("❌ Voice Call Error:", e)

def send_telegram(message):
    print("📲 Sending Telegram Alert...")
    clean_msg = message.replace(" ", "%20").replace("\n", "%0A")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={clean_msg}"
    try:
        res = urequests.get(url)
        res.close()
        print("✅ Telegram Sent!")
    except Exception as e:
        print("❌ Telegram Error:", e)

# ==========================================
# 4. INITIALIZATION & NETWORKING
# ==========================================
devices = i2c.scan()
HW61_ADDR = devices[0] if devices and devices[0] != 0x68 else 0x27

try:
    lcd = SimpleI2CLCD(i2c, HW61_ADDR)
    lcd.putstr("CONNECTING WI-FI...")
except:
    pass

try:
    mpu = MPU6050(i2c)
except:
    pass

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(WIFI_SSID, WIFI_PASS)

print(f"Connecting to {WIFI_SSID}...")
while not wifi.isconnected():
    time.sleep(0.5)
print(f"✅ Wi-Fi Connected! IP: {wifi.ifconfig()[0]}")

udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# State Variables
last_lcd_update = 0
current_page = 1
last_page_change = time.time()
last_pico_sync = 0

sos_alert_sent = False
dui_alert_sent = False
crash_alert_sent = False
crash_time = 0 # Tracks the 3-second crash buzzer

print("Helmet System Active. Monitoring...\n")

# ==========================================
# 5. MAIN RUNTIME LOOP
# ==========================================
while True:
    try:
        current_time = time.time()
        
        # --- 1. READ SENSORS ---
        sos_state = sos_switch.value()
        vib_state = vib_sensor.value()
        alcohol_level = mq3_sensor.read()
        pir_val = pir_sensor.value()
        ir_val = ir_sensor.value() 
        g_force = mpu.get_force()
        maps_link = get_maps_link()
        
        # --- 2. PICO SYNC (Every 1 Second) ---
        is_helmet_worn = True if (pir_val == 1 and ir_val == 0) else False
        if current_time - last_pico_sync >= 1:
            try:
                msg = "HELMET_ON" if is_helmet_worn else "HELMET_OFF"
                udp.sendto(msg.encode('utf-8'), (PICO_IP, PICO_PORT))
            except:
                pass 
            last_pico_sync = current_time

        # --- 3. HARDWARE ALARMS & API ALERTS ---
        is_emergency = False
        emergency_type = ""
        
        # A. Manual SOS Switch (Alert + Call + Continuous Buzzer)
        if sos_state == 0:
            is_emergency = True
            emergency_type = "SOS"
            if not sos_alert_sent:
                short_msg = f"SOS! Loc: {maps_link}"
                send_twilio_sms(short_msg)
                send_telegram(short_msg)
                call_twilio()
                sos_alert_sent = True
        else:
            sos_alert_sent = False

        # B. DUI Check (Alert + Call + Continuous Buzzer)
        if alcohol_level > ALCOHOL_THRESHOLD:
            is_emergency = True
            emergency_type = "DUI"
            if not dui_alert_sent:
                short_msg = f"DUI! Loc: {maps_link}"
                send_twilio_sms(short_msg)
                send_telegram(short_msg)
                call_twilio()
                dui_alert_sent = True
        else:
            dui_alert_sent = False
            
        # C. Crash Detection (Alert + 3-Sec Buzzer)
        if vib_state == 1 or g_force > 3.0:
            is_emergency = True
            emergency_type = "CRASH"
            if not crash_alert_sent:
                short_msg = f"CRASH! Loc: {maps_link}"
                send_twilio_sms(short_msg)
                send_telegram(short_msg)
                crash_alert_sent = True
                crash_time = current_time # Start 3-second timer
        else:
            crash_alert_sent = False

        # Siren Control
        if is_emergency:
            internal_led.value(1)
            # If it's a crash, ring buzzer ONLY for 3 seconds
            if emergency_type == "CRASH":
                if current_time - crash_time <= 3:
                    buzzer.value(1)
                else:
                    buzzer.value(0)
            else:
                buzzer.value(1) # Continuous for SOS / DUI
        else:
            internal_led.value(0)
            buzzer.value(0)

        # --- 4. 3-PAGE LCD ROTATION (Every 4 Secs) ---
        if current_time - last_page_change >= 4:
            current_page = current_page + 1 if current_page < 3 else 1
            last_page_change = current_time

        if current_time - last_lcd_update >= 0.5:
            try:
                if is_emergency:
                    # Emergency Override Screen
                    lcd.move_to(0, 0)
                    lcd.putstr(pad(f"!!! {emergency_type} DETECTED !!!"))
                    lcd.move_to(0, 1)
                    lcd.putstr(pad("CALL: +919122476011"))
                    lcd.move_to(0, 2)
                    lcd.putstr(pad("SOS ALERT SENT"))
                    lcd.move_to(0, 3)
                    lcd.putstr(pad("Please Help!"))
                else:
                    # Normal 3-Page Rotation
                    if current_page == 1:
                        lcd.move_to(0, 0)
                        lcd.putstr(pad(f"Helmet: {'WORN' if is_helmet_worn else 'EMPTY'}"))
                        lcd.move_to(0, 1)
                        lcd.putstr(pad(f"Alcohol Lvl: {alcohol_level}"))
                        lcd.move_to(0, 2)
                        lcd.putstr(pad(f"Wi-Fi: {WIFI_SSID[:13]}"))
                        lcd.move_to(0, 3)
                        lcd.putstr(pad("          >> PAGE 1/3"))
                    elif current_page == 2:
                        lcd.move_to(0, 0)
                        lcd.putstr(pad(f"G-Force: {g_force:.1f}G"))
                        lcd.move_to(0, 1)
                        # Check if we are using the live GPS or the reserve GPS
                        gps_status = "SEARCHING" if RESERVE_GPS in maps_link else "LOCKED"
                        lcd.putstr(pad(f"GPS: {gps_status}"))
                        lcd.move_to(0, 2)
                        lcd.putstr(pad(f"Sync: {PICO_IP[-6:]} OK"))
                        lcd.move_to(0, 3)
                        lcd.putstr(pad("          >> PAGE 2/3"))
                    elif current_page == 3:
                        lcd.move_to(0, 0)
                        lcd.putstr(pad("--- RAW DATA ---"))
                        lcd.move_to(0, 1)
                        lcd.putstr(pad(f"PIR:{pir_val} IR:{ir_val} VIB:{vib_state}"))
                        lcd.move_to(0, 2)
                        lcd.putstr(pad(f"SOS Switch : {sos_state}"))
                        lcd.move_to(0, 3)
                        lcd.putstr(pad("          >> PAGE 3/3"))
            except:
                pass
            last_lcd_update = current_time

        time.sleep(0.05) 

    except KeyboardInterrupt:
        buzzer.value(0)
        internal_led.value(0)
        print("\nSystem Stopped.")
        break
    except Exception as e:
        print(f"Loop Error: {e}")
        time.sleep(1)