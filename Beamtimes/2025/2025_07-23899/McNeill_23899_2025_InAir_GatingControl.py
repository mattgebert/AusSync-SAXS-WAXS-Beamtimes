# import pyvisa
import socket
import time
import datetime
import numpy as np

class AgilentB2902A:
    def __init__(self, address = "10.138.50.191", port = 5025):
        """
        Initializes the Agilent B2902A SMU communication.

        Parameters
        ----------
        address : str, optional
            The Socket IP address, by default 10.138.50.191
        """
        self.address = address
        self.port = port
        
        # Software interrupt trigger
        self.stoptrigger = False
        
        # Connect
        self.connect(address)

        # Beep up
        self.beep_up()

    def connect(self, address = None, port = None):
        address = address or self.address
        port = port or self.port
        # Define the Socket to communicate
        self.socket = socket.socket(
            socket.AF_INET, 
            socket.SOCK_STREAM
        )
        self.socket.connect(
            (address, 
             port)
        )
        self.timeout = 5000
        

    def write(self, command):
        self.socket.sendall((command + "\n").encode())

    def query(self, command, response_length = 256):
        self.write(command)
        data = self.socket.recv(response_length)
        return data

    def close(self):
        # Socket disconnection?
        self.socket.close()
        
    def beep_up(self):
        self.write(":SYST:BEEP:STAT ON")
        self.write(":SYST:BEEP 800, 0.1")
        self.write(":SYST:BEEP 1000, 0.1")
        self.write(":SYST:BEEP 1200, 0.1")
        self.write(":SYST:BEEP 1600, 0.4")

    def beep_dn(self):
        self.write(":SYST:BEEP:STAT ON")
        self.write(":SYST:BEEP 1600, 0.1")
        self.write(":SYST:BEEP 1200, 0.1")
        self.write(":SYST:BEEP 1000, 0.1")
        self.write(":SYST:BEEP 800, 0.4")
        
    def reset(self):
        """
        Resets the instrument to its default state.
        """
        self.write("*RST")
        
    def setup(self, voltage=0, measurement_time=0.001, auto_sensitivity = True, curr_range = 0.1):
        """
        Sets up the instrument for voltage sourcing and current measurement.

        Parameters
        ----------
        voltage : float, optional
            The voltage to set on the output, by default 0.
        """
        self.reset()
        # Setup the system date and time
        now = datetime.datetime.now()
        date = now.strftime("%Y,%m,%d")
        time = now.strftime("%H,%M,%S")
        self.write(f":SYST:DATE {date}")
        self.write(f":SYST:TIME {time}")
        # Set the output to voltage mode and configure the measurement settings
        self.write(":SOUR:FUNC VOLT")
        # Set the voltage level
        self.write(":SOUR:VOLT {}".format(voltage))
        # Set the measurement function to current
        self.write(":SENS:FUNC 'CURR'")
        
        # Set the compliance of the voltage
        self.write(":SENS:VOLT:PROT 10") #10 V.
        # Set the compliance of the current
        self.write(":SENS:CURR:PROT 0.1") #100 mA.
        
        # Set the measurement time
        self.write(f":SENS:CURR:APER {measurement_time:0.3f}")
        
        # Set the current range to a manual value instead of auto
        #TODO
        
        # Enable the output
        self.write(":OUTP ON")
        
    def measure(self):
        current = self.query(":meas:curr? (@1)")
        voltage = self.query(":meas:volt? (@1)")
        return (current, voltage)
    
    def run_measurement(self, 
                        turn_on_time, 
                        turn_on_voltage, 
                        turn_off_time_meas, 
                        turn_off_voltage=0, 
                        meas_interval=0.005):
        """
        Starts the measurement process.
        """
        t0 = time.time()
        self.datapoints = []
        switched = False
        while not self.stoptrigger:
            # Do measurement routine here
            t_global = time.time()
            t = t_global - t0
            # Check for switch on
            if not switched and t >= turn_on_time:
                self.write(f":sour:volt {turn_on_voltage}")
                # Finish with a beep
                self.beep_up()
                switched = True
            # Measurement
            current, voltage = self.measure()
            self.datapoints.append((t_global, current, voltage))
            
            # Delay between measurements
            time.sleep(meas_interval)
        
        # Perform stop measurement
        # Switch straight away
        self.write(f":sour:volt {turn_off_voltage}")
        self.beep_dn()
        
        t_global = time.time()
        t = t_global - t0 # global time to record
        t1 = t # check the time since turnoff
        while t < t1 + turn_off_time_meas:
            # Keep measuring
            t_global = time.time()
            t = t_global - t0
            current, voltage = self.measure()
            self.datapoints.append((t_global, current, voltage))
            # Delay between measurements
            time.sleep(meas_interval)
        
        self.datapoints = np.array(self.datapoints, dtype=float)
        # Remove the turnon time from all timestamps.
        return self.datapoints