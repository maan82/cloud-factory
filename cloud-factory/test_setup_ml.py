import unittest
import mock
import setup_ml
import requests
from requests.auth import HTTPDigestAuth


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

        setup_ml.RETRY_COUNT = 1
        url = "admin-init-url"
        host = "host"
        data = "<license/>"
        headers = {"a":"a"}
        auth = HTTPDigestAuth("username", "password")
        setup_ml.post_and_await_restart(host, url, data, headers, auth)

        mock_post.assert_called_with(url, data=data, headers=headers, allow_redirects=True, auth=auth)
        mock_get.assert_called_with("http://host:8001/admin/v1/timestamp", allow_redirects=True, auth=auth, headers=None)

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
        headers = {"a":"a"}
        auth = HTTPDigestAuth("username", "password")
        try:
            setup_ml.post_and_await_restart(host, url, data, headers, auth)
        except Exception as ex:
            self.assertEqual(ex.message, ("Timestamp has not changed after retries : %s " % setup_ml.RETRY_COUNT))

        mock_post.assert_called_with(url, data=data, headers=headers, allow_redirects=True, auth=auth)
        self.assertEqual(mock_get.call_count, setup_ml.RETRY_COUNT)

    @mock.patch("setup_ml.requests")
    def test_create_database_when_empty_db_config(self, mock_requests):
        database = {
            "database-name": "ass",
            "NumberOfforestsPerDisk": "2"
        }
        auth = HTTPDigestAuth("admin", "password")
        host_ip = "192.168.0.1"
        config = {"DataBaseConfigurations": [{
            "ass": {}
        }]}

        mock_post = mock.MagicMock(return_value=mock.MagicMock(status_code=201))
        mock_requests.post = mock_post

        setup_ml.create_database(config, auth, database, host_ip)

        mock_post.assert_called_with("http://" + host_ip + ":8002/manage/v2/databases",
                                     headers={"Content-Type": "application/json"}, data={"database-name": "ass"},
                                     allow_redirects=True, auth=auth)

    @mock.patch("setup_ml.requests")
    def test_create_database_when_non_empty_db_config(self, mock_requests):
        database = {
            "database-name": "ass",
            "NumberOfforestsPerDisk": "2"
        }
        auth = HTTPDigestAuth("admin", "password")
        host_ip = "192.168.0.1"
        config = {"DataBaseConfigurations": [{
            "ass": {
                "enabled" : "true"
            }
        }]}

        mock_post = mock.MagicMock(return_value=mock.MagicMock(status_code=201))
        mock_requests.post = mock_post

        setup_ml.create_database(config, auth, database, host_ip)

        mock_post.assert_called_with("http://" + host_ip + ":8002/manage/v2/databases",
                                     headers={"Content-Type": "application/json"}, data={"database-name": "ass", "enabled": "true"},
                                     allow_redirects=True, auth=auth)

if __name__ == '__main__':
    unittest.main()
