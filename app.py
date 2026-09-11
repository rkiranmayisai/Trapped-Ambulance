import os
import sys
import json
import time
import threading
from flask import Flask, jsonify, request, send_file, Response, render_template

# Ensure UTF-8 output on Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, template_folder=BASE_DIR, static_url_path='')


# Global thread-safe state lock
state_lock = threading.Lock()

# Initial Default State
def get_initial_state():
    return {
        "emergency_active": False,
        "ambulance_id": "AMB-911-HYD",
        "ambulance_distance": 850,  # meters from primary junction
        "ambulance_speed": 62,       # km/h
        "ambulance_heading": 45,     # degrees
        "ambulance_lat": 17.4400,
        "ambulance_lng": 78.3750,
        "hospital_lat": 17.4560,
        "hospital_lng": 78.3920,
        "current_junction": "Junction 1 - Cyber Gateway",
        "signal_state": "NORMAL_CYCLE",  # NORMAL_CYCLE, YELLOW_TRANSITION, GREEN_CORRIDOR, RECOVERY
        "all_signals": {
            "J1": {
                "id": "J1",
                "name": "Cyber Gateway Junction",
                "distance": 180,
                "state": "NORMAL_CYCLE",
                "normal_countdown": 24,
                "lat": 17.4442,
                "lng": 78.3802
            },
            "J2": {
                "id": "J2",
                "name": "Hitech Metro Crossing",
                "distance": 540,
                "state": "NORMAL_CYCLE",
                "normal_countdown": 12,
                "lat": 17.4495,
                "lng": 78.3855
            },
            "J3": {
                "id": "J3",
                "name": "Care Hospital Approach",
                "distance": 890,
                "state": "NORMAL_CYCLE",
                "normal_countdown": 38,
                "lat": 17.4540,
                "lng": 78.3900
            }
        },
        "eta_seconds": 58,
        "patient_vitals": {
            "patient_name": "Ramesh Verma (54M)",
            "heart_rate": 126,
            "spo2": 91,
            "blood_pressure": "155/100",
            "trauma_grade": "CRITICAL (Grade 1)",
            "condition": "Severe Acute Coronary Syndrome / ST-Elevation",
            "blood_group": "B+ Positive",
            "ecg_status": "Ventricular Tachycardia",
            "ot_reserved": "Trauma Bay 02 - Reserved",
            "blood_bank_ready": True,
            "surgeon_on_call": "Dr. A. Sharma (Senior Cardiologist)",
            "triage_color": "RED"
        },
        "civilian_alerts": {
            "active": False,
            "warning_distance": 500,
            "acknowledged_count": 28,
            "lane_cleared": True,
            "last_lane_update": "Lanes 1 & 2 Diverted"
        },
        "police_console": {
            "mode": "AUTOMATED_PREEMPTION", # or MANUAL_OVERRIDE
            "override_target": None,
            "time_saved_minutes": 14.8,
            "green_corridor_active": False,
            "congestion_index": "38% (Low Delay)"
        },
        "event_logs": [
            {"time": "14:40:02", "text": "System initialized. GPS & V2X Telemetry Engine Active.", "type": "info"},
            {"time": "14:40:15", "text": "Signal Nodes J1, J2, J3 connected via MQTT/WebSocket.", "type": "success"}
        ],
        "last_updated": time.time()
    }

system_state = get_initial_state()

def log_event(text, event_type="info"):
    timestamp = time.strftime("%H:%M:%S")
    system_state["event_logs"].insert(0, {"time": timestamp, "text": text, "type": event_type})
    if len(system_state["event_logs"]) > 25:
        system_state["event_logs"].pop()

# --- ROUTES ---

@app.route('/')
def unified_portal():
    return render_template('unified_app.html', state=system_state)

@app.route('/driver')
def driver_view():
    return render_template('driver.html', state=system_state)

@app.route('/civilian')
def civilian_view():
    return render_template('civilian.html', state=system_state)

@app.route('/hospital')
def hospital_view():
    return render_template('hospital.html', state=system_state)

@app.route('/police')
def police_view():
    return render_template('police.html', state=system_state)

@app.route('/guide')
def guide_view():
    guide_path = os.path.join(BASE_DIR, 'project_guide.html')
    if os.path.exists(guide_path):
        return send_file(guide_path)
    return "Project Guide not found", 404

@app.route('/pdf')
def pdf_download():
    pdf_path = os.path.join(BASE_DIR, 'Trapped_Ambulance_Project_Guide.pdf')
    if not os.path.exists(pdf_path):
        try:
            import generate_pdf
            generate_pdf.build_pdf()
        except Exception as e:
            return f"PDF generation error: {str(e)}", 500
    return send_file(pdf_path, mimetype='application/pdf')

@app.route('/manifest.json')
def manifest_file():
    return send_file(os.path.join(BASE_DIR, 'manifest.json'), mimetype='application/manifest+json')

@app.route('/sw.js')
def sw_file():
    return send_file(os.path.join(BASE_DIR, 'sw.js'), mimetype='application/javascript')

@app.route('/static/<path:filename>')
def serve_static(filename):
    file_path = os.path.join(BASE_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404

@app.route('/apk')
@app.route('/download_apk')
@app.route('/download')
@app.route('/TrappedAmbulance.apk')
def apk_download():
    apk_path = os.path.join(BASE_DIR, 'TrappedAmbulance.apk')
    if os.path.exists(apk_path):
        return send_file(apk_path, as_attachment=True, download_name='TrappedAmbulance.apk', mimetype='application/vnd.android.package-archive')
    return "APK build not found", 404



# --- SSE STREAM FOR REAL-TIME SUB-100MS SYNC ---

@app.route('/api/stream')
def sse_stream():
    def event_stream():
        last_sent_time = 0
        while True:
            with state_lock:
                current_time = system_state.get('last_updated', 0)
                # Send update whenever state changes or heartbeat every 2 seconds
                if current_time != last_sent_time or (time.time() - last_sent_time > 2.0):
                    data = json.dumps(system_state)
                    yield f"data: {data}\n\n"
                    last_sent_time = current_time
            time.sleep(0.1)
    return Response(event_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*'
    })

# --- API ENDPOINTS ---

@app.route('/api/status', methods=['GET'])
def get_status():
    with state_lock:
        return jsonify(system_state)

@app.route('/api/trigger_emergency', methods=['POST'])
def trigger_emergency():
    global system_state
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'start')
    
    with state_lock:
        if mode == 'start':
            system_state['emergency_active'] = True
            system_state['ambulance_distance'] = 380
            system_state['ambulance_speed'] = 68
            system_state['signal_state'] = 'GREEN_CORRIDOR'
            system_state['all_signals']['J1']['state'] = 'GREEN_CORRIDOR'
            system_state['all_signals']['J2']['state'] = 'YELLOW_TRANSITION'
            system_state['civilian_alerts']['active'] = True
            system_state['police_console']['green_corridor_active'] = True
            system_state['eta_seconds'] = 24
            log_event("🚨 EMERGENCY GREEN CORRIDOR INITIATED for AMB-911-HYD", "warning")
            log_event("🚦 Signal J1 (Cyber Gateway) forced to GREEN CORRIDOR. Cross-traffic stopped.", "success")
            log_event("🚗 Civilian V2X Proximity Radar broadcasting within 500m radius.", "info")

        elif mode == 'pass':
            system_state['ambulance_distance'] = 20
            system_state['signal_state'] = 'RECOVERY'
            system_state['all_signals']['J1']['state'] = 'RECOVERY'
            system_state['all_signals']['J2']['state'] = 'GREEN_CORRIDOR'
            system_state['civilian_alerts']['active'] = False
            system_state['eta_seconds'] = 6
            log_event("✅ Ambulance cleared Junction 1. Signal J1 transitioning to Recovery Cycle.", "info")
            log_event("🚦 Junction 2 preempted to GREEN CORRIDOR.", "success")

        elif mode == 'hospital_arrived':
            system_state['ambulance_distance'] = 0
            system_state['ambulance_speed'] = 0
            system_state['signal_state'] = 'NORMAL_CYCLE'
            for sig in system_state['all_signals'].values():
                sig['state'] = 'NORMAL_CYCLE'
            system_state['civilian_alerts']['active'] = False
            system_state['police_console']['green_corridor_active'] = False
            system_state['eta_seconds'] = 0
            system_state['patient_vitals']['ot_reserved'] = "Patient Received at Trauma Bay 02"
            log_event("🏥 PATIENT HANDOVER COMPLETE: Ambulance safely docked at Care Hospital ER.", "success")
            log_event("⏱️ Total Golden Hour transit time saved: 14.8 minutes.", "success")

        elif mode == 'reset':
            system_state.clear()
            system_state.update(get_initial_state())
            log_event("🔄 System reset to default standby mode.", "info")

        system_state['last_updated'] = time.time()
        return jsonify({"success": True, "state": system_state})

@app.route('/api/ambulance/telemetry', methods=['POST'])
def update_telemetry():
    data = request.get_json(silent=True) or {}
    with state_lock:
        if 'speed' in data:
            system_state['ambulance_speed'] = float(data['speed'])
        if 'distance' in data:
            dist = float(data['distance'])
            system_state['ambulance_distance'] = dist
            # Dynamic signal preemption logic
            if system_state['emergency_active']:
                if dist <= 400 and dist > 30:
                    system_state['signal_state'] = 'GREEN_CORRIDOR'
                    system_state['all_signals']['J1']['state'] = 'GREEN_CORRIDOR'
                    system_state['civilian_alerts']['active'] = True
                elif dist <= 30:
                    system_state['signal_state'] = 'RECOVERY'
                    system_state['all_signals']['J1']['state'] = 'RECOVERY'
                    system_state['civilian_alerts']['active'] = False
            # Recalculate ETA (seconds)
            spd = max(system_state['ambulance_speed'], 10)
            system_state['eta_seconds'] = int((dist / (spd * 1000 / 3600)))
        if 'lat' in data and 'lng' in data:
            system_state['ambulance_lat'] = float(data['lat'])
            system_state['ambulance_lng'] = float(data['lng'])

        system_state['last_updated'] = time.time()
        return jsonify({"success": True, "state": system_state})

@app.route('/api/ambulance/vitals', methods=['POST'])
def update_vitals():
    data = request.get_json(silent=True) or {}
    with state_lock:
        vitals = system_state['patient_vitals']
        for key in ['patient_name', 'heart_rate', 'spo2', 'blood_pressure', 'trauma_grade', 'condition', 'blood_group', 'ecg_status', 'triage_color']:
            if key in data:
                vitals[key] = data[key]
        log_event(f"📋 Patient Vitals Updated: HR={vitals.get('heart_rate')}, SpO2={vitals.get('spo2')}%, Grade={vitals.get('trauma_grade')}", "info")
        system_state['last_updated'] = time.time()
        return jsonify({"success": True, "vitals": vitals})

@app.route('/api/civilian/acknowledge', methods=['POST'])
def civilian_acknowledge():
    with state_lock:
        system_state['civilian_alerts']['acknowledged_count'] += 1
        system_state['civilian_alerts']['lane_cleared'] = True
        log_event(f"🚗 Civilian vehicle TS-09 confirmed: Lane cleared left.", "success")
        system_state['last_updated'] = time.time()
        return jsonify({"success": True, "acknowledged_count": system_state['civilian_alerts']['acknowledged_count']})

@app.route('/api/signal/override', methods=['POST'])
def signal_override():
    data = request.get_json(silent=True) or {}
    signal_id = data.get('signal_id', 'J1')
    target_state = data.get('state', 'GREEN_CORRIDOR')
    
    with state_lock:
        if signal_id in system_state['all_signals']:
            system_state['all_signals'][signal_id]['state'] = target_state
            system_state['signal_state'] = target_state
            system_state['police_console']['mode'] = 'MANUAL_OVERRIDE'
            log_event(f"👮 Police Manual Override: Signal {signal_id} set to {target_state}", "warning")
        system_state['last_updated'] = time.time()
        return jsonify({"success": True, "signal": system_state['all_signals'].get(signal_id)})

@app.route('/api/hospital/prep', methods=['POST'])
def hospital_prep():
    data = request.get_json(silent=True) or {}
    action = data.get('action', '')
    
    with state_lock:
        vitals = system_state['patient_vitals']
        if action == 'reserve_ot':
            vitals['ot_reserved'] = "Trauma Bay 01 (Confirmed Ready & Sterile)"
            log_event("🏥 Hospital ER: Trauma Bay 01 locked and prepped for incoming ambulance.", "success")
        elif action == 'ready_blood_bank':
            vitals['blood_bank_ready'] = True
            log_event(f"🩸 Blood Bank: 4 Units of {vitals.get('blood_group')} matched and placed in ER.", "success")
        elif action == 'alert_specialist':
            specialist = data.get('specialist', 'Chief Neuro & Cardiac Team')
            vitals['surgeon_on_call'] = f"{specialist} Standing by in ER Dock"
            log_event(f"👨‍⚕️ Emergency Team Alerted: {specialist} waiting at Bay Doors.", "success")
        system_state['last_updated'] = time.time()
        return jsonify({"success": True, "vitals": vitals})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("================================================================")
    print("🚑 TRAPPED AMBULANCE: FULL-STACK PWA & CLOUD DASHBOARD")
    print("================================================================")
    print(f"Master Portal:          http://localhost:{port}/")
    print(f"Ambulance Driver App:   http://localhost:{port}/driver")
    print(f"Civilian V2X Radar:     http://localhost:{port}/civilian")
    print(f"Hospital ER Hub:        http://localhost:{port}/hospital")
    print(f"Traffic Police Console: http://localhost:{port}/police")
    print(f"PDF Project Guide:      http://localhost:{port}/pdf")
    print("================================================================")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
