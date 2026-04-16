"""
field.py — Circular field model with geographic coordinate utilities.
"""

import math
from dataclasses import dataclass


EARTH_RADIUS_M = 6_371_000.0  # mean Earth radius in metres


@dataclass
class Field:
    """A circular grazing field defined by a centre point and radius."""

    lat: float        # centre latitude  (decimal degrees)
    lon: float        # centre longitude (decimal degrees)
    radius_m: float   # field radius in metres

    # ------------------------------------------------------------------ #
    #  Geographic helpers                                                  #
    # ------------------------------------------------------------------ #

    def haversine_distance(self, lat1: float, lon1: float,
                           lat2: float, lon2: float) -> float:
        """Great-circle distance in metres between two (lat, lon) points."""
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)

        a = (math.sin(dphi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
        return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))

    def distance_from_centre(self, lat: float, lon: float) -> float:
        """Distance in metres from field centre to (lat, lon)."""
        return self.haversine_distance(self.lat, self.lon, lat, lon)

    def is_inside(self, lat: float, lon: float) -> bool:
        """Return True if the point is within the field boundary."""
        return self.distance_from_centre(lat, lon) <= self.radius_m

    def offset_point(self, lat: float, lon: float,
                     bearing_deg: float, distance_m: float):
        """
        Return (lat, lon) after moving *distance_m* metres in *bearing_deg*
        direction from (lat, lon).  Uses flat-Earth approximation — accurate
        enough for field radii up to ~50 km.
        """
        bearing_rad = math.radians(bearing_deg)
        delta_lat_m = distance_m * math.cos(bearing_rad)
        delta_lon_m = distance_m * math.sin(bearing_rad)

        # 1 degree latitude ≈ 111 319 m everywhere
        new_lat = lat + delta_lat_m / 111_319.0
        # 1 degree longitude depends on latitude
        metres_per_deg_lon = 111_319.0 * math.cos(math.radians(lat))
        if metres_per_deg_lon > 0:
            new_lon = lon + delta_lon_m / metres_per_deg_lon
        else:
            new_lon = lon

        return new_lat, new_lon

    def bearing_to_centre(self, lat: float, lon: float) -> float:
        """Compass bearing (degrees, 0–360) from (lat, lon) toward field centre."""
        phi1 = math.radians(lat)
        phi2 = math.radians(self.lat)
        dlam = math.radians(self.lon - lon)

        x = math.sin(dlam) * math.cos(phi2)
        y = (math.cos(phi1) * math.sin(phi2)
             - math.sin(phi1) * math.cos(phi2) * math.cos(dlam))
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360

    def clamp_to_field(self, lat: float, lon: float, margin_m: float = 50.0):
        """
        If (lat, lon) is outside the field, push it back inside to
        (radius_m - margin_m) along the bearing toward centre.
        Returns (new_lat, new_lon, was_clamped).
        """
        dist = self.distance_from_centre(lat, lon)
        if dist <= self.radius_m:
            return lat, lon, False

        bearing = self.bearing_to_centre(lat, lon)
        safe_dist = dist - (self.radius_m - margin_m)
        new_lat, new_lon = self.offset_point(lat, lon, bearing, safe_dist)
        return new_lat, new_lon, True

    def random_point_inside(self, rng) -> tuple:
        """
        Return a uniformly random (lat, lon) inside the field.
        *rng* is a numpy.random.Generator instance.
        """
        # Uniform distribution in a disk: r = R * sqrt(U)
        r = self.radius_m * math.sqrt(rng.uniform(0, 1))
        theta = rng.uniform(0, 2 * math.pi)
        bearing_deg = math.degrees(theta)
        return self.offset_point(self.lat, self.lon, bearing_deg, r)
