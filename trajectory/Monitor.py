import time

class Monitor(object):
    """
    Mission monitor class.

    Tracks sensors and mission actions in a stepwise fashion.
    """

    def __init__(self, mission, environment):
        self.mission = mission

        self.environment = environment
        arguments = self.environment.get_arguments()
        self.settings = arguments.get_settings("mission_monitor")

        # Seconds to wait before monitoring again
        self.step_delay = self.settings.get("step_delay")

        self.sensors = self.environment.get_distance_sensors()
        self.rf_sensor = self.environment.get_rf_sensor()

        self.colors = ["red", "purple", "black"]

        self.memory_map = None
        self.plot = None

    def get_delay(self):
        """
        Retrieve the time delay in seconds that should be waited between steps.
        """

        return self.step_delay

    def use_viewer(self):
        """
        Check whether the monitor should use an interactive simulated viewer.
        """

        return self.settings.get("viewer")

    def setup(self):
        """
        Finalize setting up the monitor.

        This must be called before the `step` method is called.
        """

        self.memory_map = self.mission.get_memory_map()

        if self.settings.get("plot"):
            # Setup memory map plot
            from Plot import Plot
            self.plot = Plot(self.environment, self.memory_map)

        if self.rf_sensor is not None:
            self.rf_sensor.activate()

    def step(self, add_point=None):
        """
        Perform one step of a monitoring loop.

        `add_point` can be a callback function that accepts a Location object
        for a detected point from the distance sensors.

        The monitor must be initialized with `setup` and `start` should also
        be called.

        Returns `Fase` if the loop should be halted.
        """

        # Put the locations of the vehicles on the map for visualization. The 
        # locations are also considered "unsafe", so we cannot make a safe path 
        # that crosses one of them, excluding our own location.
        # Each vehicle has its own ID in the map to make it possible to see 
        # which vehicle is where. The ID is the RF sensor ID plus one so as to 
        # not conflict with the values used for detected obstacles.
        vehicle_locations = self.environment.get_vehicle_locations()
        for vehicle_id, location in vehicle_locations.iteritems():
            try:
                self.memory_map.set_location_value(location, vehicle_id + 1)
            except KeyError:
                print("Warning: Vehicle {} is outside of memory map ({})".format(vehicle_id, location))

        # Let the mission check its state and update its actions.
        # This is mostly used for GUIDED missions.
        self.mission.step()

        # Check all distance sensors for nearby objects. These are added to the 
        # memory map and passed through to the `add_point` callback. The 
        # mission may decide on its own whether to take safety measures based 
        # on the sensor distances.
        for i, sensor in enumerate(self.sensors):
            yaw = sensor.get_angle()
            pitch = sensor.get_pitch()
            sensor_distance = sensor.get_distance()

            if self.mission.check_sensor_distance(sensor_distance, yaw, pitch):
                location = self.memory_map.handle_sensor(sensor_distance, yaw)
                if add_point is not None:
                    add_point(location)
                if self.plot:
                    # Display the edge of the simulated object that is 
                    # responsible for the measured distance, and consequently 
                    # the point itself. This should be the closest "wall" in 
                    # the angle's direction. This is again a "cheat" for 
                    # checking if walls get visualized correctly.
                    sensor.draw_current_edge(self.plot.get_plot(), self.memory_map, self.colors[i % len(self.colors)])

                print("=== [!] Distance to object: {} m (yaw {}, pitch {}) ===".format(sensor_distance, yaw, pitch))

        # Display the current memory map interactively, if enabled.
        if self.plot:
            self.plot.plot_lines(self.mission.get_waypoints())
            self.plot.display()

        # Let the mission check the current waypoint and update its state.
        # This is mostly useful for AUTO missions.
        if not self.mission.check_waypoint():
            return False

        # Remove the vehicles from their current locations. We set it to "safe" 
        # since there is no other object here. The vehicles are placed at their 
        # (updated) location in the next step.
        for vehicle_id, location in vehicle_locations.iteritems():
            try:
                self.memory_map.set_location_value(location, vehicle_id + 1)
            except KeyError:
                pass

        return True

    def sleep(self):
        """
        Make the main monitoring thread wait for the time delay between steps.
        """

        time.sleep(self.step_delay)

    def start(self):
        """
        Start the mission.
        """

        self.mission.start()

        if self.rf_sensor is not None:
            self.rf_sensor.start()

    def stop(self):
        """
        Immediately stop the mission and clean up other monitoring devices.

        The mission cannot be continued once it is stopped.
        """

        self.mission.stop()

        if self.rf_sensor is not None:
            self.rf_sensor.stop()

        if self.plot:
            self.plot.close()
