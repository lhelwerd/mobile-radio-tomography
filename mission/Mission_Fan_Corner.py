import itertools
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

        location = self.vehicle.location
        if location.north == 0 and location.east == 0:
            self.id = 0
            self.waypoints = itertools.chain(
                # Corner rounds
                # 1: eastward straight line (on south edge)
                wpzip([], xrange(1, grid_size), fillvalue=0),
                # 2: northward straight line (on east edge)
                wpzip(xrange(1, grid_size), [], fillvalue=size),
                # 3: westward straight line (on north edge)
                wpzip([], xrange(size - 1, -1, -1), fillvalue=size),
                # 4: southward straight line (on west edge)
                wpzip(xrange(size - 1, -1, -1), [], fillvalue=0),
                # Fan beam rounds
                # 5: stand still in bottom left corner
                wpzip(
                    itertools.repeat(0, size * 2),
                    itertools.repeat(0, size * 2)
                ),
                # 6: bottom right fan beam
                itertools.chain(
                    wpzip([], xrange(1, grid_size), fillvalue=0),
                    wpzip(xrange(1, grid_size), [], fillvalue=size)
                ),
                # 7: stand still in top right corner
                wpzip(
                    itertools.repeat(size, size * 2),
                    itertools.repeat(size, size * 2)
                ),
                # 8: top left fan beam
                itertools.chain(
                    wpzip([], xrange(size - 1, -1, -1), fillvalue=size),
                    wpzip(xrange(size - 1, -1, -1), [], fillvalue=0)
                )
            )
        elif location.north == 0 and location.east == size:
            self.id = 1
            self.waypoints = itertools.chain(
                # Corner rounds
                # 1: northward straight line (on east edge)
                wpzip(xrange(1, grid_size), [], fillvalue=size),
                # 2: westward straight line (on north edge)
                wpzip([], xrange(size - 1, -1, -1), fillvalue=size),
                # 3: southward straight line (on west edge)
                wpzip(xrange(size - 1, -1, -1), [], fillvalue=0),
                # 4: eastward straight line (on south edge)
                wpzip([], xrange(1, grid_size), fillvalue=0),
                # Fan beam rounds
                # 5: top right fan beam
                itertools.chain(
                    wpzip(xrange(1, grid_size), [], fillvalue=size),
                    wpzip([], xrange(size - 1, -1, -1), fillvalue=size)
                ),
                # 6: stand still in top left corner
                wpzip(
                    itertools.repeat(size, size * 2),
                    itertools.repeat(0, size * 2)
                ),
                # 7: bottom left fan beam
                itertools.chain(
                    wpzip(xrange(size - 1, -1, -1), [], fillvalue=0),
                    wpzip([], xrange(1, grid_size), fillvalue=0)
                ),
                # 8: stand still in bottom right corner
                wpzip(
                    itertools.repeat(0, size * 2),
                    itertools.repeat(size, size * 2)
                )
            )
        else:
            raise ValueError("Vehicle is incorrectly positioned at ({},{}), must be at (0,0) or (0,{})".format(location.north, location.east, size))

    def get_points(self):
        self.waypoints = list(self.waypoints)
        return [
            LocationLocal(north, east, 0.0) for north, east in self.waypoints
        ]
