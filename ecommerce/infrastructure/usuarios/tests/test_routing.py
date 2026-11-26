from django.test import SimpleTestCase
from django.urls import Resolver404, resolve


class SecurityProbeIsolationTests(SimpleTestCase):
    def test_test_probes_are_not_available_in_production_urlconf(self):
        for path in ('/private/', '/administrator/'):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path, urlconf='backend_project.urls')
