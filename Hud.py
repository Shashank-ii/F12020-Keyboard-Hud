import hid
import time
import socket
import struct
print("hello")
# CONFIG - F1 2020 Precision Offsets
VID, PID = 0x36ae, 0xfe9c
UDP_IP, UDP_PORT = "127.0.0.1", 20777
CAR_STATUS_SIZE = 60 
TELEMETRY_SIZE = 58

class SafeKeyboardDriver:
    def __init__(self, target_path):
        self.kb = hid.device()
        self.kb.open_path(target_path)
        self.kb.set_nonblocking(1)
        self.hardware_state = {}
        
    def set_key_color(self, target_index, r, g, b):
        if self.hardware_state.get(target_index) == (r, g, b):
            return 
        packet = [0x00] * 65
        packet[1:4] = [0x06, 0x14, 0x03] 
        packet[4] = (3 * target_index) & 255
        packet[5] = ((3 * target_index) >> 8) & 255
        packet[9], packet[10], packet[11] = r, g, b
        self.kb.write(packet)
        self.hardware_state[target_index] = (r, g, b)
        time.sleep(0.001) 

    def close(self):
        self.kb.close()

def get_tire_color(wear, damage, is_strobe):
    if damage > 5: return (255, 0, 0) if is_strobe else (40, 0, 0)
    wear = max(0, min(100, wear))
    if wear < 50:
        r, g = int((wear / 50.0) * 255), 255
    else:
        r, g = 255, int(255 - ((wear - 50) / 50.0) * 255)
    return (r, g, 0)

def run_live_telemetry():
    target_path = None
    for info in hid.enumerate(VID, PID):
        if info['interface_number'] == 2:
            target_path = info['path']
            break
    if not target_path: return

    kb = SafeKeyboardDriver(target_path)
    
    # --- HARDWARE MAP ---
    REV_KEYS = [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33] 
    ERS_KEYS = [50, 51, 52] 
    
    # The Sniffed Absolute Truth: L-Shift is 84, R-Shift is 97.
    DRS_KEYS = [84, 97]     
    
    TIRE_FL, TIRE_FR, TIRE_RL, TIRE_RR = 21, 34, 105, 118 
    ALL_TIRES = [TIRE_FL, TIRE_FR, TIRE_RL, TIRE_RR]
    BOTTOM_ROW = [106, 107, 111, 115, 116, 117] 

    print("Handshake: Both Shift Keys (84 & 97) flashing Blue...")
    for k in DRS_KEYS: kb.set_key_color(k, 0, 0, 255)
    time.sleep(1.5)
    for k in DRS_KEYS: kb.set_key_color(k, 0, 0, 0)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.setblocking(False)

    live_rev_percent = 0
    live_ers_level = 0.0
    live_ers_mode = 0 
    live_tire_wears = [0, 0, 0, 0] 
    live_wing_damage = [0, 0, 0]
    live_sc_status = 0 
    live_drs_allowed = 0 
    live_drs_dist = 0 
    live_drs_active = 0  
    
    last_aux_update = 0
    rev_locked = False

    print("V41: Stealth DRS Active. Awaiting Deployment Zones.")

    try:
        while True:
            try:
                while True:
                    data, _ = sock.recvfrom(2048)
                    header = struct.unpack('<HBBBBQfIBB', data[:24])
                    p_id, p_idx = header[4], header[8]

                    if p_id == 6: # Telemetry
                        offset = 24 + (p_idx * TELEMETRY_SIZE)
                        live_drs_active = struct.unpack_from('<B', data, offset + 18)[0]
                        live_rev_percent = struct.unpack_from('<B', data, offset + 19)[0]
                        
                    elif p_id == 7: # Car Status
                        offset = 24 + (p_idx * CAR_STATUS_SIZE)
                        
                        # DRS Sniper Data
                        live_drs_allowed = struct.unpack_from('<B', data, offset + 22)[0]
                        live_drs_dist = struct.unpack_from('<H', data, offset + 23)[0]
                        
                        # V30 Restored Offsets
                        w = struct.unpack_from('<BBBB', data, offset + 25)
                        live_tire_wears = [w[2], w[3], w[0], w[1]]
                        live_wing_damage = struct.unpack_from('<BBB', data, offset + 36)
                        e = struct.unpack_from('<f', data, offset + 43)[0]
                        live_ers_level = max(0.0, min(1.0, e / 4000000.0))
                        live_ers_mode = struct.unpack_from('<B', data, offset + 47)[0]
                        
                    elif p_id == 1: # Session
                        live_sc_status = struct.unpack_from('<B', data, 148)[0]
            except BlockingIOError: pass 

            curr_t = time.perf_counter()
            strobe_fast = (curr_t % 0.2) < 0.1 

            # --- RPM BAR ---
            if live_rev_percent >= 99:
                if not rev_locked:
                    for i, k in enumerate(REV_KEYS):
                        col = (0,255,0) if i<4 else ((255,0,0) if i<8 else (255,0,255))
                        kb.set_key_color(k, *col)
                    rev_locked = True
            else:
                rev_locked = False
                scaled = (live_rev_percent / 100.0) * 12.0
                for i, k in enumerate(REV_KEYS):
                    r,g,b = (0,0,0)
                    if scaled >= i + 1:
                        r,g,b = (0,255,0) if i<4 else ((255,0,0) if i<8 else (255,0,255))
                    kb.set_key_color(k, r, g, b)

            # --- AUX DASH ---
            if curr_t - last_aux_update >= 0.1:
                # 1. EARLY-WARNING DRS (Both Shift Keys)
                drs_c = (0, 0, 0)
                if live_drs_active == 1:
                    drs_c = (0, 255, 0) # Green when Open
                elif live_drs_allowed == 1 or live_drs_dist > 0:
                    drs_c = (255, 255, 0) # Bright Yellow Warning
                
                for k in DRS_KEYS: kb.set_key_color(k, *drs_c)

                # 2. ERS METER
                for i, k in enumerate(ERS_KEYS):
                    template = (0, 255, 255) if live_ers_mode == 2 else (255, 255, 0)
                    key_min, key_max = i / 3.0, (i + 1) / 3.0
                    if live_ers_level >= key_max: kb.set_key_color(k, *template)
                    elif live_ers_level <= key_min: kb.set_key_color(k, 0, 0, 0)
                    else:
                        fade = (live_ers_level - key_min) / (1/3.0)
                        kb.set_key_color(k, int(template[0]*fade), int(template[1]*fade), int(template[2]*fade))
                
                # 3. SC & TIRES
                sc_c = (255, 150, 0) if (live_sc_status > 0 and strobe_fast) else (0,0,0)
                for k in BOTTOM_ROW: kb.set_key_color(k, *sc_c)
                for i, k in enumerate(ALL_TIRES):
                    dmg = live_wing_damage[0] if i == 0 else (live_wing_damage[1] if i == 1 else live_wing_damage[2])
                    kb.set_key_color(k, *get_tire_color(live_tire_wears[i], dmg, strobe_fast))
                
                last_aux_update = curr_t

            time.sleep(0.005)

    except KeyboardInterrupt:
        for k in REV_KEYS + ERS_KEYS + BOTTOM_ROW + ALL_TIRES + DRS_KEYS: kb.set_key_color(k, 0, 0, 0)
    finally: kb.close(); sock.close()

if __name__ == "__main__": run_live_telemetry()