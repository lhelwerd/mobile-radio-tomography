from Robot_Vehicle import Robot_Vehicle
from ..location.Line_Follower_Arduino import Line_Follower_Arduino
from ..trajectory.Servo import Servo

class Robot_Vehicle_Arduino(Robot_Vehicle):
    """
    Robot vehicle that is connected via a serial interface via an Arduino.
    """

    _line_follower_class = Line_Follower_Arduino

    def __init__(self, arguments, geometry):
        super(Robot_Vehicle_Arduino, self).__init__(arguments, geometry)

        self.settings = arguments.get_settings("vehicle_robot_arduino")

        # PWM range for both motors (minimum and maximum values)
        self._speed_pwms = self.settings.get("speed_pwms")
        # Speed range for both motors in m/s
        self._speeds = self.settings.get("speeds")

        # Servo objects for tracking and converting speed PWM values. The pin 
        # numbers are dummy.
        self._speed_servos = [Servo(i, self._speeds, self._speed_pwms) for i in range(2)]

        self._serial_connection = self._line_follower.get_serial_connection()

    def setup(self):
        self._serial_connection.reset_output_buffer()

    def set_speeds(left_speed, right_speed, left_forward=True, right_forward=True):
        output = ""
        for i, speed, forward in [(0, left_speed, left_forward), (1, right_speed, right_forward)]:
            if not forward:
                speed = -speed

            pwm = self._speed_servos[i].get_pwm(speed)
            self._speed_servos[i].set_current_pwm(pwm)
            output += "{} ".format(pwm)

        self._serial_connection.write("{}\n".format(output.strip())
