import os
import subprocess
import serial
import thread
import time
import random
import copy
import Queue
from xbee import ZigBee
from XBee_Packet import XBee_Packet
from XBee_Sensor import XBee_Sensor
from XBee_TDMA_Scheduler import XBee_TDMA_Scheduler
from ..settings import Arguments

class XBee_Sensor_Physical(XBee_Sensor):
    def __init__(self, arguments, thread_manager, usb_manager,
                 location_callback, receive_callback, valid_callback):
        """
        Initialize the sensor.
        """

        super(XBee_Sensor_Physical, self).__init__(thread_manager, location_callback,
                                                   receive_callback, valid_callback)

        self._usb_manager = usb_manager

        if isinstance(arguments, Arguments):
            self.settings = arguments.get_settings("xbee_sensor_physical")
        else:
            raise ValueError("'settings' must be an instance of Arguments")

        self.id = 0
        self.scheduler = XBee_TDMA_Scheduler(self.id, arguments)
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
        self._active = False

        # Prepare the packet and sensor data.
        self._custom_packet_limit = self.settings.get("custom_packet_limit")
        self._number_of_sensors = self.settings.get("number_of_sensors")
        self._sensors = self.settings.get("sensors")
        self._loop_delay = self.settings.get("loop_delay")
        for index, address in enumerate(self._sensors):
            self._sensors[index] = address.decode("string_escape")

    def _setup(self):
        """
        Setup the serial connection and join the network.
        """

        port = self.settings.get("port")
        if port != "":
            self._serial_connection = self._usb_manager.get_xbee_device(port)
        else:
            self._serial_connection = self._usb_manager.get_xbee_device()

        self._sensor = ZigBee(self._serial_connection, callback=self._receive)
        time.sleep(self.settings.get("startup_delay"))
        self._join()

    def activate(self):
        """
        Activate the sensor by sending a packet if it is not a ground station.
        The sensor always receives packets asynchronously.
        """

        super(XBee_Sensor_Physical, self).activate()

        self._active = True
        self._setup()
        thread.start_new_thread(self._loop, ())

    def _loop(self):
        """
        Execute the sensor loop. This runs in a separate thread.
        """

        try:
            while self._active:
                if not self._joined:
                    continue

                if self.id > 0 and time.time() >= self._next_timestamp:
                    self._next_timestamp = self.scheduler.get_next_timestamp()
                    self._send()

                time.sleep(self._loop_delay)
        except:
            super(XBee_Sensor_Physical, self).interrupt()

    def deactivate(self):
        """
        Deactivate the sensor and close the serial connection.
        """

        super(XBee_Sensor_Physical, self).deactivate()

        self._active = False
        self._sensor.halt()
        self._serial_connection.close()

    def enqueue(self, packet, to=None):
        """
        Enqueue a custom packet to send to another XBee device.
        """

        if not isinstance(packet, XBee_Packet):
            raise TypeError("Only XBee_Packet objects can be enqueued")

        if packet.is_private():
            raise ValueError("Private packets cannot be enqueued")

        if to != None:
            self._queue.put({
                "packet": packet,
                "to": to
            })
        else:
            # No destination ID has been provided, therefore we broadcast
            # the packet to all sensors in the network except for ourself
            # and the ground sensor.
            for to_id in xrange(1, self.settings.get("number_of_sensors") + 1):
                if to_id == self.id:
                    continue

                self._queue.put({
                    "packet": copy.deepcopy(packet),
                    "to": to_id
                })

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
                packet.set("specification", "ntp")
                packet.set("sensor_id", self.id)
                packet.set("timestamp_1", time.time())
                packet.set("timestamp_2", 0)
                packet.set("timestamp_3", 0)
                packet.set("timestamp_4", 0)

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
        a = packet.get("timestamp_2") - packet.get("timestamp_1")
        b = packet.get("timestamp_3") - packet.get("timestamp_4")
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

        # Create and send the RSSI broadcast packets.
        packet = self.make_rssi_broadcast_packet()
        packet.set("sensor_id", self.id)

        for index in xrange(1, self._number_of_sensors + 1):
            if index == self.id:
                continue

            self._sensor.send("tx", dest_addr_long=self._sensors[index],
                              dest_addr="\xFF\xFE", frame_id="\x00",
                              data=packet.serialize())

        # Send custom packets to their destination. Since the time slots are
        # limited in length, so is the number of custom packets we transfer
        # in each sweep.
        limit = self._custom_packet_limit
        while not self._queue.empty():
            if limit == 0:
                break

            limit -= 1
            item = self._queue.get()
            self._sensor.send("tx", dest_addr_long=self._sensors[item["to"]],
                              dest_addr="\xFF\xFE", frame_id="\x00",
                              data=item["packet"].serialize())

        # Send the sweep data to the ground sensor and clear the list
        # for the next round.
        for frame_id in self._data.keys():
            packet = self._data[frame_id]
            if packet.get("rssi") is None:
                continue

            self._sensor.send("tx", dest_addr_long=self._sensors[0],
                              dest_addr="\xFF\xFE", frame_id="\x00",
                              data=packet.serialize())

            self._data.pop(frame_id)

    def _receive(self, raw_packet):
        """
        Receive and process a raw packet from another sensor in the network.
        """

        if raw_packet["id"] == "rx":
            packet = XBee_Packet()
            packet.unserialize(raw_packet["rf_data"])

            if self.check_receive(packet):
                return

            if packet.get("specification") == "ntp":
                if packet.get("timestamp_2") == 0:
                    packet.set("timestamp_2", time.time())
                    packet.set("timestamp_3", time.time())
                    self._sensor.send("tx", dest_addr_long=self._sensors[packet.get("sensor_id")],
                                      dest_addr="\xFF\xFE", frame_id="\x00",
                                      data=packet.serialize())
                else:
                    packet.set("timestamp_4", time.time())
                    self._ntp(packet)

                return

            if self.id == 0:
                print("[{}] Ground station received {}".format(time.time(), packet.get_all()))
                return

            # Synchronize the scheduler using the timestamp in the packet.
            self._next_timestamp = self.scheduler.synchronize(packet)

            # Create the packet for the ground station.
            ground_station_packet = self.make_rssi_ground_station_packet(packet)

            # Generate a frame ID to be able to match this packet and the
            # associated RSSI (DB command) request.
            frame_id = chr(random.randint(1, 255))
            self._data[frame_id] = ground_station_packet

            # Request the RSSI value for the received packet.
            self._sensor.send("at", command="DB", frame_id=frame_id)
        elif raw_packet["id"] == "at_response":
            if raw_packet["command"] == "DB":
                # RSSI value has been received. Update the original packet.
                if raw_packet["frame_id"] in self._data:
                    original_packet = self._data[raw_packet["frame_id"]]
                    original_packet.set("rssi", ord(raw_packet["parameter"]))
            elif raw_packet["command"] == "SH":
                # Serial number (high) has been received.
                if self._address is None:
                    self._address = raw_packet["parameter"]
                elif raw_packet["parameter"] not in self._address:
                    self._address = raw_packet["parameter"] + self._address
                    self._address_set = True
            elif raw_packet["command"] == "SL":
                # Serial number (low) has been received.
                if self._address is None:
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
