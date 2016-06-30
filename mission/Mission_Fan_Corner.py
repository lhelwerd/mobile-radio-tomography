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
                # 2: top right fan beam
                itertools.chain(
                    wpzip([], xrange(1, grid_size), fillvalue=size),
                    wpzip(xrange(size - 1, -1, -1), [], fillvalue=size)
                ),
                # 3: northward straight line (on east edge)
                wpzip(xrange(1, grid_size), [], fillvalue=size),
                # 4: wait in top right corner
                wpzip(
                    itertools.repeat(size, size * 2),
                    itertools.repeat(size, size * 2)
                ),
                # 5: westward straight line (on north edge)
                wpzip([], xrange(size - 1, -1, -1), fillvalue=size),
                # 6: wait in top left corner
                wpzip(
                    itertools.repeat(size, size * 2),
                    itertools.repeat(0, size * 2)
                ),
                # 7: eastward straight line (on north edge)
                wpzip([], xrange(1, grid_size), fillvalue=size),
                # 8alt: westward half straight line (on north edge)
                wpzip([], xrange(size - 1, mid - 1, -1), fillvalue=size),
                # 9alt: wait on top edge for one and a half the size
                wpzip(
                    itertools.repeat(size, size + mid),
                    itertools.repeat(mid, size + mid)
                ),
                # 10alt: fan beam at right side
                itertools.chain(
                    wpzip([], xrange(mid + 1, grid_size), fillvalue=size),
                    wpzip(xrange(size - 1, -1, -1), [], fillvalue=size),
                    wpzip([], xrange(size - 1, mid - 1, -1), fillvalue=0)
                ),
                # 11alt: wait on bottom edge
                wpzip(
                    itertools.repeat(0, size + long_mid*2),
                    itertools.repeat(mid, size + long_mid*2)
                ),
                # 12alt: fan beam at left side
                itertools.chain(
                    wpzip([], xrange(mid - 1, -1, -1), fillvalue=0),
                    wpzip(xrange(1, grid_size), [], fillvalue=0),
                    wpzip([], xrange(1, mid + 1), fillvalue=size)
                ),
                # 13alt: wait on top edge for half the size
                wpzip(
                    itertools.repeat(size, mid),
                    itertools.repeat(mid, mid)
                ),
                # 14alt: fan beam at left side excluding bottom half size
                itertools.chain(
                    wpzip([], xrange(mid - 1, -1, -1), fillvalue=size),
                    wpzip(xrange(size - 1, -1, -1), [], fillvalue=0)
                )
            )
        elif location.north == 0 and location.east == size:
            self.id = 1
            self.waypoints = itertools.chain(
                # 1: westward straight line (on south edge)
                wpzip([], xrange(size - 1, -1, -1), fillvalue=0),
                # 2: wait in bottom left corner
                wpzip(
                    itertools.repeat(0, size * 2),
                    itertools.repeat(0, size * 2)
                ),
                # 3: eastward straight line (on south edge)
                wpzip([], xrange(1, grid_size), fillvalue=0),
                # 4: bottom left fan beam
                itertools.chain(
                    wpzip([], xrange(size - 1, -1, -1), fillvalue=0),
                    wpzip(xrange(1, grid_size), [], fillvalue=0)
                ),
                # 5: southward straight line (on west edge)
                wpzip(xrange(size - 1, -1, -1), [], fillvalue=0),
                # 6: bottom right fan beam
                itertools.chain(
                    wpzip([], xrange(1, grid_size), fillvalue=0),
                    wpzip(xrange(1, grid_size), [], fillvalue=size)
                ),
                # 7: southward straight line (on east edge)
                wpzip(xrange(size - 1, -1, -1), [], fillvalue=size),
                # 8alt: wait in bottom right corner for half the size
                wpzip(
                    itertools.repeat(0, long_mid),
                    itertools.repeat(size, long_mid)
                ),
                # 9alt: fan beam at bottom side excluding right half size
                itertools.chain(
                    wpzip([], xrange(size - 1, -1, -1), fillvalue=0),
                    wpzip(xrange(1, mid + 1), [], fillvalue=0)
                ),
                # 10alt: wait at left edge for right side fan beam
                wpzip(
                    itertools.repeat(mid, size + long_mid*2),
                    itertools.repeat(0, size + long_mid*2)
                ),
                # 11alt: fan beam at top side
                itertools.chain(
                    wpzip(xrange(mid + 1, grid_size), [], fillvalue=0),
                    wpzip([], xrange(1, grid_size), fillvalue=size),
                    wpzip(xrange(size - 1, mid - 1, -1), [], fillvalue=size)
                ),
                # 12alt: wait at right edge for left side fan beam
                wpzip(
                    itertools.repeat(mid, size + mid*2),
                    itertools.repeat(size, size + mid*2)
                ),
                # 13alt: southward straight line for half a size (on east edge)
                wpzip(xrange(mid - 1, -1, -1), [], fillvalue=size),
                # 14alt: wait at bottom right for one and a half the size
                wpzip(
                    itertools.repeat(0, size + mid),
                    itertools.repeat(size, size + mid)
                )
            )
        else:
            raise ValueError("Vehicle is incorrectly positioned at ({},{}), must be at (0,0) or (0,{})".format(location.north, location.east, size))

    def get_points(self):
        self.waypoints = list(self.waypoints)
        return [
            LocationLocal(north, east, 0.0) for north, east in self.waypoints
        ]
