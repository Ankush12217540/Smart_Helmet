import machine
import time

print("Booting Standalone Motor Controller...")

# ==========================================
# 1. HARDWARE PINS
# ==========================================
# Relay controls the heavy power to the motor
relay = machine.Pin(14, machine.Pin.OUT)
relay.value(0) # Ensure motor is OFF when the board boots up

# Ignition button (using PULL_DOWN so 1 = Pressed, 0 = Unpressed)
btn_ign = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)

# ==========================================
# 2. MAIN RUNTIME LOOP
# ==========================================
ignition_on = False
btn_last_state = 0

print("--- SYSTEM READY ---")
print("Press the physical push button to toggle the motor ON/OFF.\n")

while True:
    try:
        # Read the current state of the button
        btn_current_state = btn_ign.value()
        
        # Check if button was JUST pressed (transitioning from 0 to 1)
        if btn_current_state == 1 and btn_last_state == 0:
            
            # Toggle the motor state
            ignition_on = not ignition_on 
            relay.value(1 if ignition_on else 0)
            
            print(f"🏍️ Motor is now: {'ON' if ignition_on else 'OFF'}")
                
            # Debounce delay (prevents the button from bouncing and triggering twice)
            time.sleep(0.3) 

        # Save the current state to compare during the next loop
        btn_last_state = btn_current_state
        
        # Keep the loop running fast but give the CPU a tiny rest
        time.sleep(0.05) 
        
    except KeyboardInterrupt:
        relay.value(0)
        print("\nMotor Controller Stopped.")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)