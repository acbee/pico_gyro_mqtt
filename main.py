from imu import MPU6050
from machine import I2C, Pin, RTC
from mpy_env import load_env, get_env
from time import localtime, sleep
from umqttsimple import MQTTClient
import network, sys, ubinascii, urequests

sleep(5)

# Settings
to_screen = 1
to_file   = 0
to_mqtt   = 1
decimals  = 2
accel_urt = 0
accel_sda = 0
accel_scl = 1
client_id = ubinascii.hexlify(machine.unique_id())

# Settings from env.json 
load_env()
mqtt_srvr = get_env("mqtt_srvr")
mqtt_port = get_env("mqtt_port")
mqtt_user = get_env("mqtt_user")
mqtt_pass = get_env("mqtt_pass")
ax_ptopic = get_env("ax_ptopic")
ay_ptopic = get_env("ay_ptopic")
az_ptopic = get_env("az_ptopic")
gx_ptopic = get_env("gx_ptopic")
gy_ptopic = get_env("gy_ptopic")
gz_ptopic = get_env("gz_ptopic")
tp_ptopic = get_env("tp_ptopic")
ofilename = get_env("ofilename")
wifi_ssid = get_env("wifi_ssid")
wifi_pass = get_env("wifi_pass")

# Print variables
def print_variable(variable_name, colon_position=0):
    key = variable_name
    val = globals()[variable_name]
    print("{}".format(key) + (" " * max(0, colon_position - len(key))), ":", val)

print("Configuration")
colon_position = 11
print_variable("wifi_ssid", colon_position)
print_variable("wifi_pass", colon_position)
print_variable("mqtt_srvr", colon_position)
print_variable("ax_ptopic", colon_position)
print_variable("ay_ptopic", colon_position)
print_variable("az_ptopic", colon_position)
print_variable("gx_ptopic", colon_position)
print_variable("gy_ptopic", colon_position)
print_variable("gz_ptopic", colon_position)
print_variable("tp_ptopic", colon_position)
print_variable("ofilename", colon_position)
print()

# Startup
sleep(3)
led = machine.Pin("LED", machine.Pin.OUT)
led.off()

# Start MPU6050 accelerometer
print("Accelerometer starting ... ", end="")
i2c = I2C(accel_urt, sda=Pin(accel_sda), scl=Pin(accel_scl)) #, freq=400000)
imu = MPU6050(i2c)
print("Done!")

# Connect to wireless network
print("Connecting to network %s ..." %wifi_ssid, end="")
nic = network.WLAN(network.STA_IF)
nic.active(True)
counter = 0
while True:
    led.on()
    nic.connect(wifi_ssid, wifi_pass)
    sleep(1)
    if nic.isconnected():
        print(" Connected!")
        led.off()
        break;
    else:
        print(".", end="")
        led.off()
        sleep(1)
        counter = counter + 1
        if counter == 30:
            # reboot and try again
            machine.reset()

def current_date_time_string():
    rtc = RTC()
    timestamp = rtc.datetime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (timestamp[0:3] + timestamp[4:7])

def set_time():
    import json
    # Set the RTC using API @ "http://worldtimeapi.org/api/timezone/America/Toronto"
    api_url  = "http://worldtimeapi.org/api/timezone/America/Toronto"
    api_key  = "unixtime" # name of json key
    response = ""
    unixtime = 0
    response = urequests.get(api_url)
    if response.status_code == 200:
        #print(response.text)
        data = json.loads(response.text)
        unixtime = int(data[api_key])
        #print("unixtime: %s" %unixtime)

    unixtimeAdjusted = unixtime - (3600 * 4) # four hours
    try:     
        #print("Setting time using value " + str(unixtime) + " adjusted to " + str(unixtimeAdjusted))
        from time import gmtime
        from machine import RTC
        tm = gmtime(unixtimeAdjusted)
        rtc = RTC()
        rtc.datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
        return 1
    except: 
        print("Unable to set time using value " + str(unixtime) + " adjusted to " + str(unixtimeAdjusted))
        return None

# Set the RTC using API
set_time()
print("Synchronized time with API server: %s" %current_date_time_string())

# Create file to store data
if to_file == 1:
    file = open(ofilename, "w")
    print("File %s created/opened to store data" %ofilename)

# MQTT subroutines
def mqtt_subscribe_callback(topic, msg):
    print((topic, msg))

def mqtt_connect_and_subscribe(client_id, mqtt_srvr, topic_sub, mqtt_subscribe_callback):
    client = MQTTClient(client_id, mqtt_srvr)
    client.set_callback(mqtt_subscribe_callback)
    client.connect()
    client.subscribe(topic_sub)
    #print('Connected to %s MQTT broker, subscribed to %s topic' %(mqtt_srvr, topic_sub))
    return client

def mqtt_connect(client_id, mqtt_srvr, mqtt_port, mqtt_user, mqtt_pass):
    client = MQTTClient(client_id, mqtt_srvr, int(mqtt_port), mqtt_user, mqtt_pass)
    client.connect()
    #print("Connected to MQTT broker %s" %mqtt_srvr)
    #print("Publishing to MQTT topic %s" %topic_pub)
    return client

if to_mqtt == 1:
    counter = 0
    print("Connecting to MQTT broker %s ..." %mqtt_srvr, end="")
    while True:
        led.on()
        try: 
            client = mqtt_connect(client_id, mqtt_srvr, mqtt_port, mqtt_user, mqtt_pass)
            if client:
                print("\nConnected!")
                led.off()
                break;
            else:
                counter = counter + 1
                print(".", end="")
                sleep(5)
        except: 
            counter = counter + 1
            print(".", end="")
            sleep(5)

        if counter == 30:
            # reboot and try again
            print("\nUnable to connect. Restarting ... ")
            machine.reset()

# Loop forever
print()
print("Looping ... ")
mqtt_fail_count = 0
while True:
    ax = round(imu.accel.x, decimals)
    ay = round(imu.accel.y, decimals)
    az = round(imu.accel.z, decimals)
    gx = round(imu.gyro.x,  decimals)
    gy = round(imu.gyro.y,  decimals)
    gz = round(imu.gyro.z,  decimals)
    tp = round(imu.temperature, decimals)

    timestring = current_date_time_string()
    line = timestring + "," + str(ax) + "," + str(ay) + "," + str(az) + "," + str(gx) + "," + str(gy) + "," + str(gz) + "," + str(tp)

    # Screen
    if to_screen == 1: 
        print(timestring + "     ", end="")
        print(str(ax) + (" " * max(0, 10 - len(str(ax)))), end="")
        print(str(ay) + (" " * max(0, 10 - len(str(ay)))), end="")
        print(str(az) + (" " * max(0, 10 - len(str(az)))), end="")
        print(str(gx) + (" " * max(0, 10 - len(str(gx)))), end="")
        print(str(gy) + (" " * max(0, 10 - len(str(gy)))), end="")
        print(str(gz) + (" " * max(0, 10 - len(str(gz)))), end="")
        print(str(tp) + (" " * max(0, 10 - len(str(tp)))), end="")
    
    # File
    if to_file == 1: 
        file.write(line + "\n")
        print("f ", end="")
    
    # MQTT
    if to_mqtt == 1:
        try:
            client.publish(ax_ptopic, str(ax))
            client.publish(ay_ptopic, str(ay))
            client.publish(az_ptopic, str(az))
            client.publish(gx_ptopic, str(gx))
            client.publish(gy_ptopic, str(gy))
            client.publish(gz_ptopic, str(gz))
            client.publish(tp_ptopic, str(tp))
            print("m ", end="")
        except OSError as e:
            mqtt_fail_count = mqtt_fail_count + 1
            print("MQTT Publish Error! Attempt " + str(mqtt_fail_count), end="")
            if mqtt_fail_count > 29:
                # reboot and try again
                print("\nUnable to connect. Restarting ... ")
                sleep(1)
                machine.reset()

    print()
    sleep(1)
