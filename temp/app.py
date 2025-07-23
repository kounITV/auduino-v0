# Humy_Temp_LCD_web.ino  아두이노 코드 
from flask import Flask, render_template, request, redirect, jsonify
import threading
import serial
import serial.tools.list_ports
import psycopg2
import time


# === set connect PostgreSQL ===
conn = psycopg2.connect(
    dbname="sensor_data",
    user="postgres",
    password="",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

# === check and create sensor_log table and ac_status column ===
cursor.execute("""
SELECT column_name 
FROM information_schema.columns 
WHERE table_name='sensor_log' AND column_name='ac_status';
""")
if not cursor.fetchone():
    cursor.execute("""
    ALTER TABLE sensor_log ADD COLUMN ac_status VARCHAR(10);
    """)
    conn.commit()

# === Flask app ===
app = Flask(__name__)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/latest')
def api_latest():
    cursor.execute("SELECT temp, humidity, discomfort_index, ac_status, timestamp FROM sensor_log ORDER BY timestamp DESC LIMIT 20")
    rows = cursor.fetchall()
    logs = [
        {
            'temp': row[0],
            'humidity': row[1],
            'discomfort_index': row[2],
            'ac_status': row[3],
            'timestamp': row[4].strftime('%Y-%m-%d %H:%M:%S')
        }
        for row in rows
    ]
    return jsonify({'logs': logs})

@app.route('/toggle_ac', methods=['POST'])
def toggle_ac():
    action = request.form['action']
    ac_status = 'AC ON' if action == 'on' else 'AC OFF'
    try:
        arduino.write(b'1' if action == 'on' else b'0')
    except Exception as e:
        print("Arduino write failed:", e)

    cursor.execute(
        "INSERT INTO sensor_log (temp, humidity, discomfort_index, ac_status) VALUES (%s, %s, %s, %s)",
        (0.0, 0.0, 0.0, ac_status)
    )
    conn.commit()
    return redirect('/')

# === receive serial data ===

from threading import Lock
serial_lock = Lock()
last_temp, last_humi, last_di = None, None, None

# find serial port for Arduino
def receive_serial_data():
    global arduino, last_temp, last_humi, last_di
    def find_arduino_port():
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if 'Arduino' in port.description or 'usbserial' in port.device or 'wchusbserial' in port.device:
                print(f"Arduino found on port : {port.device}")
                return port.device
    try:
        arduino_port = find_arduino_port()
        arduino = serial.Serial(arduino_port, 2400)
        time.sleep(2)
        print("Serial Receiver Started")
    except Exception as e:
        print("Serial init failed:", e)
        return

    while True:
        try:
            with serial_lock:
                waiting = arduino.in_waiting
            if waiting > 0:
                with serial_lock:
                    line = arduino.readline().decode(errors="ignore").strip()
                print(f"[DEBUG] Received Raw Line: {line}")

                if line.count(',') != 2:
                    print(f"[DEBUG] Invalid format line skipped: {line}")
                    continue

                parts = line.split(',')
                if len(parts) == 3:
                    try:
                        temp = float(parts[0].strip())
                        humi = float(parts[1].strip())
                        di = float(parts[2].strip())

                        if 10 < temp < 60 and 10 <= humi <= 100:
                            if (temp, humi, di) != (last_temp, last_humi, last_di):
                                last_temp, last_humi, last_di = temp, humi, di

                                ac_status = "AC ON" if di >= 75 else "AC OFF"

                                with serial_lock:
                                    arduino.write(b'1' if di >= 75 else b'0')

                                cursor.execute(
                                    "INSERT INTO sensor_log (temp, humidity, discomfort_index, ac_status) VALUES (%s, %s, %s, %s)",
                                    (temp, humi, di, ac_status)
                                )
                                conn.commit()

                                print(f"Saved → Temp:{temp}, Humi:{humi}, DI:{di:.2f}, Status:{ac_status}")
                            else:
                                print(f"[DEBUG] Duplicate data ignored: Temp={temp}, Humi={humi}, DI={di}")
                        else:
                            print(f"[DEBUG] Ignored invalid range: Temp={temp}, Humi={humi}")

                    except ValueError:
                        print(f"[DEBUG] ValueError during conversion: {parts}")
            else:
                print("[DEBUG] No data waiting on serial port.")
            time.sleep(1)

        except Exception as e:
            print("Error in serial reading loop:", e)
            time.sleep(1)


if __name__ == '__main__':
    serial_thread = threading.Thread(target=receive_serial_data, daemon=True)
    serial_thread.start()
    app.run(debug=True, port=5500, use_reloader=False)