import unittest

from flight_delay_explorer.utils import cancellation_reason_label, hhmm_to_hour, hhmm_to_label, time_of_day_from_hour


class UtilsTestCase(unittest.TestCase):
    def test_hhmm_to_label(self) -> None:
        self.assertEqual(hhmm_to_label(5), "00:05")
        self.assertEqual(hhmm_to_label(730), "07:30")
        self.assertEqual(hhmm_to_label(1545), "15:45")
        self.assertEqual(hhmm_to_label(2400), "24:00")

    def test_hhmm_to_hour(self) -> None:
        self.assertEqual(hhmm_to_hour(5), 0)
        self.assertEqual(hhmm_to_hour(730), 7)
        self.assertEqual(hhmm_to_hour(1545), 15)
        self.assertEqual(hhmm_to_hour(2400), 0)

    def test_time_of_day_from_hour(self) -> None:
        self.assertEqual(time_of_day_from_hour(2), "Night")
        self.assertEqual(time_of_day_from_hour(9), "Morning")
        self.assertEqual(time_of_day_from_hour(15), "Afternoon")
        self.assertEqual(time_of_day_from_hour(21), "Evening")

    def test_cancellation_reason_label(self) -> None:
        self.assertEqual(cancellation_reason_label("A"), "Carrier")
        self.assertEqual(cancellation_reason_label("B"), "Weather")
        self.assertEqual(cancellation_reason_label("C"), "National Air System")
        self.assertEqual(cancellation_reason_label("D"), "Security")
        self.assertEqual(cancellation_reason_label(""), "Unknown")


if __name__ == "__main__":
    unittest.main()
