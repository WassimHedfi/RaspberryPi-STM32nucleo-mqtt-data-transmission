import logging.handlers
import time
import os
import serial  # Import the serial library for UART communication
from tb_gateway_mqtt import TBDeviceMqttClient

ACCESS_TOKEN = "TEST_TOKEN"
THINGSBOARD_SERVER = 'demo.thingsboard.io'

# UART configuration
UART_PORT = '/dev/ttyUSB0'  # Replace with your device's UART port
UART_BAUDRATE = 115200

logging.basicConfig(level=logging.DEBUG)

client = None

# default blinking period
period = 1.0

# Initialize serial communication
ser = serial.Serial(UART_PORT, UART_BAUDRATE)

# callback function that will call when we will change value of our Shared Attribute
def attribute_callback(result, _):
    global period
    print(result)
    # make sure that you paste YOUR shared attribute name
    period = result.get('blinkingPeriod', 1.0)

# callback function that will call when we will send RPC
def rpc_callback(id, request_body):
    # request body contains method and other parameters
    print(request_body)
    method = request_body.get('method')
    if method == 'getTelemetry':
        attributes, telemetry = get_data()
        client.send_attributes(attributes)
        client.send_telemetry(telemetry)
    else:
        print('Unknown method: ' + method)

def get_data():
    # Read acceleration data from UART
    ser.flushInput()  # Clear input buffer to ensure new data
    line = ser.readline().decode('utf-8').strip()  # Read and decode a line of data
    try:
        accel_x, accel_y, accel_z = map(float, line.split())  # Parse acceleration values
    except ValueError:
        accel_x, accel_y, accel_z = 0.0, 0.0, 0.0  # Default to zero if parsing fails
        print("Error reading acceleration data")

    cpu_usage = round(float(os.popen('''grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage }' ''').readline().replace('\n', '').replace(',', '.')), 2)
    ip_address = os.popen('''hostname -I''').readline().replace('\n', '').replace(',', '.')[:-1]
    mac_address = os.popen('''cat /sys/class/net/*/address''').readline().replace('\n', '').replace(',', '.')
    processes_count = os.popen('''ps -Al | grep -c bash''').readline().replace('\n', '').replace(',', '.')[:-1]
    swap_memory_usage = os.popen("free -m | grep Swap | awk '{print ($3/$2)*100}'").readline().replace('\n', '').replace(',', '.')[:-1]
    ram_usage = float(os.popen("free -m | grep Mem | awk '{print ($3/$2) * 100}'").readline().replace('\n', '').replace(',', '.')[:-1])
    st = os.statvfs('/')
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    boot_time = os.popen('uptime -p').read()[:-1]
    avg_load = (cpu_usage + ram_usage) / 2

    attributes = {
        'ip_address': ip_address,
        'macaddress': mac_address
    }
    telemetry = {
        'cpu_usage': cpu_usage,
        'processes_count': processes_count,
        'disk_usage': used,
        'RAM_usage': ram_usage,
        'swap_memory_usage': swap_memory_usage,
        'boot_time': boot_time,
        'avg_load': avg_load,
        'accel_x': accel_x,
        'accel_y': accel_y,
        'accel_z': accel_z
    }
    print(attributes, telemetry)
    return attributes, telemetry

# request attribute callback
def sync_state(result, exception=None):
    global period
    if exception is not None:
        print("Exception: " + str(exception))
    else:
        period = result.get('shared', {'blinkingPeriod': 1.0})['blinkingPeriod']

def main():
    global client
    client = TBDeviceMqttClient(THINGSBOARD_SERVER, username=ACCESS_TOKEN)
    client.connect()
    client.request_attributes(shared_keys=['blinkingPeriod'], callback=sync_state)
    
    # now attribute_callback will process shared attribute request from server
    sub_id_1 = client.subscribe_to_attribute("blinkingPeriod", attribute_callback)
    sub_id_2 = client.subscribe_to_all_attributes(attribute_callback)

    # now rpc_callback will process rpc requests from server
    client.set_server_side_rpc_request_handler(rpc_callback)

    while not client.stopped:
        attributes, telemetry = get_data()
        client.send_attributes(attributes)
        client.send_telemetry(telemetry)
        time.sleep(period)

if __name__ == '__main__':
    if ACCESS_TOKEN != "TEST_TOKEN":
        main()
    else:
        print("Please change the ACCESS_TOKEN variable to match your device access token and run script again.")
