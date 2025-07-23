import serial
import time
import threading
from collections import deque
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.graph_objs as go

# Serial settings
PORT = '/dev/cu.usbserial-3140'
BAUD = 2400

# Buffers
max_len = 20
temps = deque(maxlen=max_len)
humis = deque(maxlen=max_len)
dis = deque(maxlen=max_len)
timestamps = deque(maxlen=max_len)
ac_statuses = deque(maxlen=max_len)

lock = threading.Lock()

# Serial reader thread
def read_serial():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=2)
        time.sleep(2)
        while True:
            line = ser.readline().decode('utf-8').strip()
            if line:
                print("Raw:", line)  # Debug line
                try:
                    temp, humi, di = map(float, line.split(','))
                    ac_status = "ON" if di >= 75.0 else "OFF"
                    now = time.strftime('%H:%M:%S')
                    with lock:
                        temps.append(temp)
                        humis.append(humi)
                        dis.append(di)
                        timestamps.append(now)
                        ac_statuses.append(ac_status)
                except ValueError:
                    print("Could not parse:", line)
    except Exception as e:
        print("Serial error:", e)

thread = threading.Thread(target=read_serial)
thread.daemon = True
thread.start()

# Dash app setup
app = dash.Dash(__name__)
app.title = "Arduino DHT Dashboard"

app.layout = html.Div([
    # html.H2("🌡️ Arduino DHT11 Live Dashboard"),
    dcc.Graph(id='live-graph'),
    html.Br(),
    # html.H4("📋 Recent Sensor Data"),
    dash_table.DataTable(
        id='live-table',
        columns=[
            {"name": "Time", "id": "time"},
            {"name": "Temp (°C)", "id": "temp"},
            {"name": "Humidity (%)", "id": "humi"},
            {"name": "Index", "id": "di"},
            {"name": "AC Status", "id": "ac"},
        ],
        style_cell={'textAlign': 'center'},
        style_header={'fontWeight': 'bold'},
    ),
    dcc.Interval(id='interval-component', interval=3000, n_intervals=0),
])

@app.callback(
    [Output('live-graph', 'figure'),
     Output('live-table', 'data')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    with lock:
        trace_temp = go.Scatter(x=list(timestamps), y=list(temps), name='Temp (°C)', line=dict(color='red'))
        trace_humi = go.Scatter(x=list(timestamps), y=list(humis), name='Humidity (%)', line=dict(color='blue'))
        trace_di = go.Scatter(x=list(timestamps), y=list(dis), name='Index', line=dict(color='green'))

        table_data = [
            {
                "time": t,
                "temp": f"{te:.2f}",
                "humi": f"{h:.2f}",
                "di": f"{d:.2f}",
                "ac": a
            }
            for t, te, h, d, a in zip(timestamps, temps, humis, dis, ac_statuses)
        ]

    figure = {
        'data': [trace_temp, trace_humi, trace_di],
        'layout': go.Layout(
            xaxis=dict(title='Time'),
            yaxis=dict(title='Values'),
            margin=dict(l=40, r=20, t=40, b=40),
            legend=dict(x=0, y=1.1, orientation='h'),
            hovermode='closest'
        )
    }

    return figure, table_data

if __name__ == '__main__':
    app.run(debug=True)
