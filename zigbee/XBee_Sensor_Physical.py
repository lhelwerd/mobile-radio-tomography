import os
import subprocess
import serial
import time
import random
import copy
import Queue
from xbee import ZigBee
from XBee_Packet import XBee_Packet
from XBee_Sensor import XBee_Sensor
from ..settings import Arguments, Settings

class XBee_Sensor_Physical(XBee_Sensor):
    def __init__(self, settings, scheduler, location_callback=None,
                 receive_callback=None):
        """
        Initialize the sensor.
        """

        if isinstance(settings, Arguments):
            self.settings = settings.get_settings("xbee_sensor_physical")
        elif isinstance(settings, Settings):
            self.settings = settings
        else:
            raise ValueError("'settings' must be an instance of Settings or Arguments")

        if location_callback == None or receive_callback == None:
            raise TypeError("Missing required location and receive callbacks")

        self.id = 0
        self.scheduler = scheduler
        self._location_callback = location_callback
        self._receive_callback = receive_callback
        self._next_timestamp = 0
        self._serial_connection = None
        self._node_identifier_set = False
        self._address_set = False
        self._joined = False
        self._synchronized = False
        self._sensor = None
        self._address = None
        self._data = {}
        self._queue = Queue.Queue()
        self._verbose = self.settings.get("verbose")

        # Prepare the packet and sensor data.
        self._custom_packet_limit = self.settings.get("custom_packet_limit")
        self._number_of_sensors = self.settings.get("number_of_sensors")
        self._sensors = self.settings.get("sensors")
        for index, address in enumerate(self._sensors):
            self._sensors[index] = address.decode("string_escape")

    def activate(self):
        """
        Activate the sensor by sending a packet if it is not a ground station.
        The sensor always receives packets asynchronously.
        """

        # Lazily initialize the serial connection and ZigBee object.
        if self._serial_connection == None and self._sensor == None:
            self._serial_connection = serial.Serial(self.settings.get("port"),
                                                    self.settings.get("baud_rate"))
            self._sensor = ZigBee(self._serial_connection, callback=self._receive)
            time.sleep(self.settings.get("startup_delay"))
            self._join()

        if not self._joined:
            return

        if self.id > 0 and time.time() >= self._next_timestamp:
            self._next_timestamp = self.scheduler.get_next_timestamp()
            self._send()

    def deactivate(self):
        """
        Deactivate the sensor and close the serial connection.
        """

        self._sensor.halt()
        self._serial_connection.close()

    def enqueue(self, packet):
        """
        Enqueue a custom packet to send to another XBee device.
        Valid packets must be XBee_Packet objects and must contain
        the ID of the destination XBee device.
        """

        if not isinstance(packet, XBee_Packet):
            raise TypeError("Only XBee_Packet objects can be enqueued")

        packet.set("_type", "custom")
        if packet.get("to_id") != None:
            self._queue.put(packet)
        else:
            # No destination ID has been provided, therefore we broadcast
            # the packet to all sensors in the network except for ourself
            # and the ground sensor.
            for index in xrange(1, self.settings.get("number_of_sensors") + 1):
                if index == self.id:
                    continue

                packet.set("to_id", index)
                self._queue.put(copy.deepcopy(packet))

    def _join(self):
        """
        Join the network and set this sensor's ID and address before sending.
        """

        response_delay = self.settings.get("response_delay")

        while not self._node_identifier_set:
            self._sensor.send("at", command="NI")
            time.sleep(response_delay)

        while not self._address_set:
            self._sensor.send("at", command="SH")
            time.sleep(response_delay)
            self._sensor.send("at", command="SL")
            time.sleep(response_delay)

        while not self._joined:
            self._sensor.send("at", command="AI")
            time.sleep(response_delay)

        if self.id > 0 and self.settings.get("synchronize"):
            # Synchronize the clock with the ground station's clock before
            # sending messages. This avoids clock skew caused by the fact that
            # the Raspberry Pi devices do not have an onboard real time clock.
            while not self._synchronized:
                packet = XBee_Packet()
                packet.set("_type", "ntp")
                packet.set("_from_id", self.id)
                packet.set("_t1", time.time())

                # Send the NTP packet to the ground station.
                self._sensor.send("tx", dest_addr_long=self._sensors[0],
                                  dest_addr="\xFF\xFE", frame_id="\x00",
                                  data=packet.serialize())
                time.sleep(self.settings.get("ntp_delay"))

    def _ntp(self, packet):
        """
        Perform the NTP (network time protocol) algorithm to synchronize
        the sensor's clock with the ground sensor's clock.

        Refer to the original paper "Internet time synchronization: the
        network time protocol" by David L. Mills (IEEE, 1991) for more
        information.
        """

        # Calculate the clock offset.
        a = packet.get("_t2") - packet.get("_t1")
        b = packet.get("_t3") - packet.get("_t4")
        clock_offset = float(a + b) / 2

        # Apply the offset to the current clock to synchronize.
        synchronized = time.time() + clock_offset

        # Update the system clock with the synchronized clock.
        with open(os.devnull, 'w') as FNULL:
            subprocess.call(["date", "-s", "@{}".format(synchronized)],
                            stdout=FNULL, stderr=FNULL)

        self._synchronized = True
        return clock_offset

    def _send(self):
        """
        Send a packet to each other sensor in the network.
        """

        packet = XBee_Packet()
        packet.set("_from", self._location_callback())
        packet.set("_from_id", self.id)
        packet.set("_timestamp", time.time())
        for index in xrange(1, self._number_of_sensors + 1):
            if index == self.id:
                continue

            self._sensor.send("tx", dest_addr_long=self._sensors[index],
                              dest_addr="\xFF\xFE", frame_id="\x00",
                              data=packet.serialize())

            if self._verbose:
                print("--> Sending to sensor {}.".format(index))

        # Send custom packets to their destination. Since the time slots are
        # limited in length, so is the number of custom packets we transfer
        # in each sweep.
        limit = self._custom_packet_limit
        while not self._queue.empty():
            if limit == 0:
                break

            limit -= 1
            packet = self._queue.get()
            to_id = packet.get("to_id")
            self._sensor.send("tx", dest_addr_long=self._sensors[to_id],
                              dest_addr="\xFF\xFE", frame_id="\x00",
                              data=packet.serialize())

        # Send the sweep data to the ground sensor and clear the list
        # for the next round.
        for frame_id in self._data.keys():
            packet = self._data[frame_id]
            if packet.get("_rssi") == None:
                continue

            self._sensor.send("tx", dest_addr_long=self._sensors[0],
                              dest_addr="\xFF\xFE", frame_id="\x00",
                              data=packet.serialize())

            self._data.pop(frame_id)

            if self._verbose:
                print("--> Sending to ground station.")

    def _receive(self, raw_packet):
        """
        Receive and process a raw packet from another sensor in the network.
        """

        if raw_packet["id"] == "rx":
            try:
                packet = XBee_Packet()
                packet.unserialize(raw_packet["rf_data"])
            except:
                # The raw packet is malformed, so drop it.
                return

            if packet.get("_type") == "custom":
                packet.unset("_type")
                packet.unset("to_id")
                self._receive_callback(packet)
                return

            if packet.get("_type") == "ntp":
                if packet.get("_t2") == None:
                    packet.set("_t2", time.time())
                    packet.set("_t3", time.time())
                    self._sensor.send("tx", dest_addr_long=self._sensors[packet.get("_from_id")],
                                      dest_addr="\xFF\xFE", frame_id="\x00",
                                      data=packet.serialize())
                else:
                    packet.set("_t4", time.time())
                    self._ntp(packet)

                return

            if self.id == 0:
                print("[{}] Ground station received {}".format(time.time(), packet.serialize()))
                return

            if self._verbose:
                print("<-- Received from sensor {}.".format(packet.get("_from_id")))

            # Synchronize the scheduler using the timestamp in the packet.
            self._next_timestamp = self.scheduler.synchronize(packet)

            # Sanitize and complete the packet for the ground station.
            packet.set("_to", self._location_callback())
            packet.unset("_from_id")
            packet.unset("_timestamp")

            # Generate a frame ID to be able to match this packet and the
            # associated RSSI (DB command) request.
            frame_id = chr(random.randint(1, 255))
            self._data[frame_id] = packet

            # Request the RSSI value for the received packet.
            self._sensor.send("at", command="DB", frame_id=frame_id)
        elif raw_packet["id"] == "at_response":
            if raw_packet["command"] == "DB":
                # RSSI value has been received. Update the original packet.
                if raw_packet["frame_id"] in self._data:
                    original_packet = self._data[raw_packet["frame_id"]]
                    original_packet.set("_rssi", ord(raw_packet["parameter"]))
            elif raw_packet["command"] == "SH":
                # Serial number (high) has been received.
                if self._address == None:
                    self._address = raw_packet["parameter"]
                elif raw_packet["parameter"] not in self._address:
                    self._address = raw_packet["parameter"] + self._address
                    self._address_set = True
            elif raw_packet["command"] == "SL":
                # Serial number (low) has been received.
                if self._address == None:
                    self._address = raw_packet["parameter"]
                elif raw_packet["parameter"] not in self._address:
                    self._address = self._address + raw_packet["parameter"]
                    self._address_set = True
            elif raw_packet["command"] == "NI":
                # Node identifier has been received.
                self.id = int(raw_packet["parameter"])
                self.scheduler.id = self.id
                self._node_identifier_set = True
            elif raw_packet["command"] == "AI":
                # Association indicator has been received.
                if raw_packet["parameter"] == "\x00":
                    self._joined = True
