import math
import sys
from Mission_Browse import Mission_Browse
from Mission_Square import Mission_Square
from ..location.AStar import AStar

class Mission_Pathfind(Mission_Browse, Mission_Square):
    """
    Mission that moves around in a square mission while avoiding detected
    objects, updating the mission waypoints to move in a quick detour path
    generated by an A* algorithm.
    """

    def add_commands(self):
        pass

    def check_waypoint(self):
        return True

    def start(self):
        super(Mission_Pathfind, self).start()
        self.points = self.get_points()
        self.current_point = -1
        self.next_waypoint = 0
        self.browsing = False
        self.rotating = False
        self.start_yaw = self.yaw
        self.padding = self.settings.get("padding")
        self.sensor_dist = sys.float_info.max

        self._astar = AStar(self.geometry, self.memory_map)

    def get_waypoints(self):
        return self.points

    def distance_to_point(self):
        if self.current_point < 0:
            return 0

        point = self.points[self.current_point]
        return self.environment.get_distance(point)

    def step(self):
        if self.current_point >= len(self.points):
            return

        if self.browsing:
            super(Mission_Pathfind, self).step()
            done = self.geometry.check_angle(self.start_yaw, self.yaw,
                                             self.yaw_angle_step * math.pi/180)
            if done:
                self.browsing = False

                points = self.astar(self.vehicle.location.global_relative_frame,
                                    self.points[self.next_waypoint])
                if not points:
                    raise RuntimeError("Could not find a suitable path to the next waypoint.")

                self.points[self.current_point:self.next_waypoint] = points
                self.next_waypoint = self.current_point + len(points)
                self.vehicle.speed = self.speed
                self.vehicle.simple_goto(self.points[self.current_point])
                self.rotating = True
                self.start_yaw = self.vehicle.attitude.yaw
        elif self.rotating:
            # Keep track of rotating due to a goto command.
            near = self.geometry.check_angle(self.start_yaw,
                                             self.vehicle.attitude.yaw,
                                             self.yaw_angle_step * math.pi/180)
            if near:
                self.rotating = False
                if self.check_scan():
                    return
            else:
                self.start_yaw = self.vehicle.attitude.yaw

        distance = self.distance_to_point()
        print("Distance to current point ({}): {} m".format(self.current_point, distance))
        if self.current_point < 0 or distance <= self.closeness:
            if self.current_point == self.next_waypoint:
                print("Waypoint reached.")
                self.next_waypoint = self.next_waypoint + 1

            self.current_point = self.current_point + 1
            if self.current_point >= len(self.points):
                print("Reached final point.")
                return

            print("Next point ({}): {}".format(self.current_point, self.points[self.current_point]))

            self.vehicle.simple_goto(self.points[self.current_point])

    def check_sensor_distance(self, sensor_distance, yaw, pitch):
        close = super(Mission_Pathfind, self).check_sensor_distance(sensor_distance, yaw, pitch)

        # Do not start scanning if we already are or if we are rotating because 
        # of a goto command.
        self.sensor_dist = sensor_distance
        if not self.browsing and not self.rotating:
            self.check_scan()

        return close

    def check_scan(self):
        if self.sensor_dist < 2 * self.padding + self.closeness:
            print("Start scanning due to closeness.")
            self.send_global_velocity(0,0,0)
            self.browsing = True
            self.start_yaw = self.yaw = self.vehicle.attitude.yaw
            return True

        return False

    def astar(self, start, goal):
        closeness = min(self.sensor_dist - self.padding,
                        self.padding + self.closeness)

        return self._astar.assign(start, goal, closeness)
