"""
fortunaisk Test
"""

# Django
from django.test import TestCase


class Testfortunaisk(TestCase):
    """
    Testfortunaisk
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Test setup
        :return:
        :rtype:
        """

        super().setUpClass()

    def test_fortunaisk(self):
        """
        Dummy test function
        :return:
        :rtype:
        """

        self.assertEqual(True, True)
