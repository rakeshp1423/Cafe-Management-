from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_health_check_returns_success_when_database_is_reachable(self):
        response = self.client.get('/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_health_check_only_allows_get(self):
        response = self.client.post('/health/')

        self.assertEqual(response.status_code, 405)

    def test_health_check_reports_unavailable_database(self):
        with self.assertLogs('core.views', level='ERROR'):
            with patch('core.views.connection.cursor', side_effect=OperationalError):
                response = self.client.get('/health/')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
