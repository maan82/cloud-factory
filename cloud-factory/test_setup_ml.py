import unittest
import mock
import setup_ml
import requests

class TestSetupML(unittest.TestCase):

    @mock.patch("setup_ml.requests")
    def test_post_and_await_restart_should_init_wait_timestamp_change(self, mock_requests):
        xml_response = \
        """<restart xmlns="http://marklogic.com/manage">
              <last-startup host-id="13544732455686476949">
                2013-05-15T09:01:43.019261-07:00
              </last-startup>
              <link>
                <kindref>timestamp</kindref>
                <uriref>/admin/v1/timestamp</uriref>
              </link>
              <message>Check for new timestamp to verify host restart.</message>
            </restart>"""

        mock_post = mock.MagicMock(return_value=mock.MagicMock(status_code=202, text=xml_response))
        mock_requests.post = mock_post
        mock_get = mock.MagicMock(side_effect=iter(
            [mock.MagicMock(status_code=200, text="2013-05-15T09:01:43.019261-07:00"), Exception,
             mock.MagicMock(status_code=200, text="2015-05-15T09:01:43.019261-07:00")]))
        mock_requests.get = mock_get

        setup_ml.RETRY_COUNT=1
        url = "admin-init-url"
        host = "host"
        data = "<license/>"
        setup_ml.post_and_await_restart(host, url, data)

        mock_post.assert_called_with(url, data=data, timeout=60, allow_redirects=True)
        mock_get.assert_called_with("http://host:8001/admin/v1/timestamp", timeout=60, allow_redirects=True)

    @mock.patch("setup_ml.requests")
    def test_post_and_await_restart_should_raise_on_max_retry(self, mock_requests):
        xml_response = \
        """<restart xmlns="http://marklogic.com/manage">
              <last-startup host-id="13544732455686476949">
                2013-05-15T09:01:43.019261-07:00
              </last-startup>
              <link>
                <kindref>timestamp</kindref>
                <uriref>/admin/v1/timestamp</uriref>
              </link>
              <message>Check for new timestamp to verify host restart.</message>
            </restart>"""

        mock_post = mock.MagicMock(return_value=mock.MagicMock(status_code=202, text=xml_response))
        mock_requests.post = mock_post
        mock_get = mock.MagicMock(side_effect=iter([Exception]))
        mock_requests.get = mock_get

        setup_ml.RETRY_COUNT = 1
        url = "admin-init-url"
        host = "host"
        data = "<license/>"
        setup_ml.post_and_await_restart(host, url, data)

        mock_post.assert_called_with(url, data=data, timeout=60, allow_redirects=True)
        self.assertEqual(mock_get.call_count, setup_ml.RETRY_COUNT)

if __name__ == '__main__':
    unittest.main()
