import unittest

from app import GeoPoint, build_search_blob, choose_best_location, haversine_miles


class AppTests(unittest.TestCase):
    def test_haversine_distance_is_reasonable(self) -> None:
        nyc = (40.7128, -74.0060)
        philly = (39.9526, -75.1652)
        distance = haversine_miles(nyc[0], nyc[1], philly[0], philly[1])
        self.assertGreater(distance, 75)
        self.assertLess(distance, 110)

    def test_search_blob_normalizes_text(self) -> None:
        blob = build_search_blob("Parable of the Sower", "Octavia Butler", "9780446675505")
        self.assertEqual(blob, "parable of the sower octavia butler 9780446675505")

    def test_exif_location_beats_browser_location(self) -> None:
        exif_location = GeoPoint(39.29, -76.61, "photo_exif", 0.99)
        browser_location = GeoPoint(39.30, -76.62, "browser_gps", 0.9)
        chosen = choose_best_location(exif_location, browser_location)
        self.assertEqual(chosen.source, "photo_exif")


if __name__ == "__main__":
    unittest.main()
