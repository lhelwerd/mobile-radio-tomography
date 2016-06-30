import itertools
import math
from dronekit import LocationLocal
from Mission_Auto import Mission_Auto
from ..vehicle.Robot_Vehicle import Robot_Vehicle

class Mission_Fan_Corner(Mission_Auto):
    """
    A mission that performs fan beam and corner measurements on a grid using
    a `Robot_Vehicle`.
    """

    def setup(self):
        super(Mission_Fan_Corner, self).setup()

        if not isinstance(self.vehicle, Robot_Vehicle):
            raise ValueError("Mission_Fan_Corner only works with robot vehicles")

        wpzip = itertools.izip_longest
        grid_size = int(self.size)
        # Last coordinate index of the grid in both directions
        size = grid_size - 1
        mid = size / 2
        long_mid = int(math.ceil(size / 2.0))

        location = self.vehicle.location
        if location.north == 0 and location.east == 0:
            self.id = 0
            self.waypoints = itertools.chain(
                # 1: northward straight line (on west edge)
                wpzip(xrange(1, grid_size), [], fillvalue=0),
                # 2: eastward straight line (on north edge)
                wpzip([], xrange(1, grid_size), fillvalue=size),
                # 3: southward straight line (on east edge)
                wpzip(xrange(size - 1, -1, -1), [], fillvalue=size),
                # 4: westward straight line (on south edge)
                wpzip([], xrange(size - 1, -1, -1), fillvalue=0),
                # 5: northward straight line (on west edge) for half the size
                wpzip(xrange(1, mid + 1), [], fillvalue=0),
                # 6: fan beam at top side
                itertools.chain(
                    wpzip(xrange(mid + 1, grid_size), [], fillvalue=0),
                    wpzip([], xrange(1, grid_size), fillvalue=size),
                    wpzip(xrange(size - 1, mid - 1, -1), [], fillvalue=size)
                ),
                # 7: wait at right edge for left side fan beam
                wpzip(
                    itertools.repeat(mid, size + long_mid*2),
                    itertools.repeat(size, size + long_mid*2)
                ),
                # 8: fan beam at bottom side
                itertools.chain(
                    wpzip(xrange(mid - 1, -1, -1), [], fillvalue=size),
                    wpzip([], xrange(size - 1, -1, -1), fillvalue=0),
                    wpzip(xrange(1, mid + 1), [], fillvalue=0)
                ),
                # 9: wait at left edge for right side fan beam
                wpzip(
                    itertools.repeat(mid, size + mid*2),
                    itertools.repeat(0, size + mid*2)
                ),
                # 10: southward straight line (on west edge) for half the size
                wpzip(xrange(mid - 1, -1, -1), [], fillvalue=0)
            )
        elif location.north == 0 and location.east == size:
            self.id = 1
            self.waypoints = itertools.chain(
                # 1: westward straight line (on south edge)
                wpzip([], xrange(size - 1, -1, -1), fillvalue=0),
                # 2: northward straight line (on west edge)
                wpzip(xrange(1, grid_size), [], fillvalue=0),
                # 3: eastward straight line (on north edge)
                wpzip([], xrange(1, grid_size), fillvalue=size),
                # 4: southward straight line (on east edge)
                wpzip(xrange(size - 1, -1, -1), [], fillvalue=size),
                # 5: westward straight line (on south edge) for half the size
                wpzip([], xrange(size - 1, long_mid - 1, -1), fillvalue=0),
                # 6: wait on bottom edge
                wpzip(
                    itertools.repeat(0, size + long_mid*2),
                    itertools.repeat(long_mid, size + long_mid*2)
                ),
                # 7: fan beam at left side
                itertools.chain(
                    wpzip([], xrange(long_mid - 1, -1, -1), fillvalue=0),
                    wpzip(xrange(1, grid_size), [], fillvalue=0),
                    wpzip([], xrange(1, long_mid + 1), fillvalue=size)
                ),
                # 8: wait on top edge
                wpzip(
                    itertools.repeat(size, size + mid*2),
                    itertools.repeat(long_mid, size + mid*2)
                ),
                # 9: fan beam at right side
                itertools.chain(
                    wpzip([], xrange(long_mid + 1, grid_size), fillvalue=size),
                    wpzip(xrange(size - 1, -1, -1), [], fillvalue=size),
                    wpzip([], xrange(size - 1, long_mid - 1, -1), fillvalue=0)
                ),
                # 10: eastward straight line (on south edge) for half the size
                wpzip([], xrange(long_mid + 1, grid_size), fillvalue=0)
            )
        else:
            raise ValueError("Vehicle is incorrectly positioned at ({},{}), must be at (0,0) or (0,{})".format(location.north, location.east, size))

    def get_points(self):
        self.waypoints = list(self.waypoints)
        return [
            LocationLocal(north, east, 0.0) for north, east in self.waypoints
        ]
