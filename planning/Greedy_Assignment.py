import itertools
import numpy as np

class Greedy_Assignment(object):
    """
    Synchronized traveling salesmen's tasks assignment problem algorithm.

    We use a greedy strategy to appoint a number of vehicles to visit a number
    of waypoint pairs. It does not matter which vehicle visits which waypoint,
    but each waypoint within a pair must be visited by different vehicles at the
    same moment in time (or they have to wait for the other vehicle to arrive).
    We want to minimize the time loss due to this synchronization as well as
    the time needed to visit the waypoint pairs, which can be done in any order.

    The time is calculated using the Manhattan distance in this class. Other
    implementations could add in the time needed for turning and synchronization
    or use a different distance function.
    """

    def __init__(self, arguments, geometry):
        self._settings = arguments.get_settings("planning_assignment")
        self._geometry = geometry

        self._home_locations = self._settings.get("vehicle_home_locations")
        self._number_of_vehicles = len(self._home_locations)

        self._vehicle_pairs = list(
            itertools.permutations(range(1, self._number_of_vehicles + 1), r=2)
        )

    def _get_closest_pair(self, current_positions, positions):
        distances = np.array([
            [
                # Given that both vehicles operate at the same time and 
                # synchronize at the next waypoint, the time needed depends on 
                # the longest distance that either vehicle needs to move
                abs(current_positions[vehicle-1] - positions[:, i, :]).max(axis=1)
                for i, vehicle in enumerate(vehicle_pair)
            ]
            for vehicle_pair in self._vehicle_pairs
        ])

        totals = distances.sum(axis=1)
        indices = np.unravel_index(np.argmin(totals), totals.shape)
        return indices, totals[indices]

    def assign(self, positions_pairs):
        """
        Assign the vehicles with current positions `home_positions` an ordering
        of the position pairs to be visited. `positions_pairs` must be a numpy
        array of size (Nx2x2), where N is the number of pairs, and the other
        dimensions encompass the pairs and the coordinates of each position,
        respectively.

        The returned values are the assignment, which is a dictionary with
        vehicle indexes and an ordered list of position coordinates to visit,
        and the total distance needed for this assignment according to the
        algorithm.
        """

        positions = np.array(positions_pairs)
        current_positions = list(self._home_locations)

        assignment = dict([
            (i, []) for i in range(1, self._number_of_vehicles + 1)
        ])
        total_distance = 0

        while len(positions) > 0:
            # The index of the distances matrix and the distance value itself.
            idx, distance = self._get_closest_pair(current_positions, positions)
            # The chosen vehicle pair and the chosen measurement positions pair
            vehicle_pair, closest_pair = idx

            # Determine the synchronization (waits) between the two vehicles in 
            # the chosen vehicle pair. There are always two permutations here.
            syncs = itertools.permutations(self._vehicle_pairs[vehicle_pair])
            for i, sync_pair in enumerate(syncs):
                vehicle, other_vehicle = sync_pair

                new_position = list(positions[closest_pair, i, :])

                # Create an assignment containing the full position and the 
                # other vehicle's wait ID.
                assignment[vehicle].append(new_position + [0, other_vehicle])
                current_positions[vehicle-1] = new_position

            total_distance += distance

            positions = np.delete(positions, closest_pair, axis=0)

        return assignment, total_distance
