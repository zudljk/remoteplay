import unittest
from unittest.mock import patch, Mock
from remoteplay.common import check_state, request_get, request_patch


class TestCommon(unittest.TestCase):


    @patch('remoteplay.common.requests.get')
    def test_check_state(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '{"state": "running"}'
        machine_id = "your_machine_id"
        api_key = "your_api_key"
        expected_state = "running"
        self.assertEqual(check_state(machine_id, api_key), expected_state)

    @patch('remoteplay.common.requests.get')
    def test_request_get(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '{"state": "running"}'
        path = "your_path"
        api_key = "your_api_key"
        expected_response = {"state": "running"}
        self.assertEqual(request_get(path, api_key), expected_response)

    @patch('remoteplay.common.requests.patch')
    def test_request_patch(self, mock_patch):
        mock_patch.return_value.status_code = 200
        mock_patch.return_value.text = '{"status": "success"}'
        path = "your_path"
        api_key = "your_api_key"
        expected_response = {"status": "success"}
        self.assertEqual(request_patch(path, api_key), expected_response)


if __name__ == '__main__':
    unittest.main()
