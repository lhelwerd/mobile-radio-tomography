try:
    import RPIO
except (ImportError, SystemError):
    RPIO = None

from Robot_Vehicle import Robot_Vehicle
from ..location.Line_Follower_Arduino import Line_Follower_Arduino
from ..trajectory.Servo import Servo

class Robot_Vehicle_Arduino(Robot_Vehicle):
    """
    Robot vehicle that is connected via a serial interface to an Arduino.

    To be used with the "zumo_serial" Arduino program.

    The Arduino passes through reflectance sensor measurements which are read by
    the `Line_Follower_Arduino` class, while the `Robot_Vehicle_Arduino` sends
    motor speeds to the Arduino that are passed through to the motor control.
    """

    _line_follower_class = Line_Follower_Arduino

    def __init__(self, arguments, geometry, thread_manager, usb_manager):
        super(Robot_Vehicle_Arduino, self).__init__(arguments, geometry, thread_manager, usb_manager)

        self.settings = arguments.get_settings("vehicle_robot_arduino")

        # PWM range for both motors (minimum and maximum values)
        self._speed_pwms = self.settings.get("speed_pwms")
        # Speed range for both motors in m/s
        self._speeds = self.settings.get("speeds")

        # Servo objects for tracking and converting speed PWM values. The pin 
        # numbers are dummy.
        self._speed_servos = [Servo(i, self._speeds, self._speed_pwms) for i in range(2)]

        self._serial_connection = usb_manager.get_ttl_device()
        self._current_speed = (0, 0, True, True)

    def setup(self):
        self._serial_connection.reset_output_buffer()

    @property
    def use_simulation(self):
        return RPIO is None

    def activate(self):
        super(Robot_Vehicle_Arduino, self).activate()
        self._serial_connection.write("START\n")
        self._serial_connection.flush()

    def _reset(self):
        # Turn off motors.
        self.set_speeds(0, 0)

    def deactivate(self):
        self._reset()
        super(Robot_Vehicle_Arduino, self).deactivate()

    def _format_speeds(self, left_speed, right_speed, left_forward, right_forward):
        output = ""
        for i, speed, forward in [(0, left_speed, left_forward), (1, right_speed, right_forward)]:
            if not forward:
                speed = -speed

            pwm = self._speed_servos[i].get_pwm(speed)
            self._speed_servos[i].set_current_pwm(pwm)
            output += "{} ".format(int(pwm))

        return output.strip()

    def set_speeds(self, left_speed, right_speed, left_forward=True, right_forward=True):
        new_speed = (left_speed, right_speed, left_forward, right_forward)
        if self._current_speed == new_speed:
            # Avoid sending the same message multiple times after each other, 
            # since the Arduino will keep at the same speed until a different 
            # message appears.
            return

        self._current_speed = new_speed
        output = self._format_speeds(*new_speed)

        self._serial_connection.write("{}\n".format(output))

    def set_servo(self, servo, pwm):
        if RPIO is not None:
            RPIO.PWM.set_servo(servo.pin, pwm)

        servo.set_current_pwm(pwm)
