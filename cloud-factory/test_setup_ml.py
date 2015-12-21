import json
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

        auth = HTTPDigestAuth("admin", "password")
        host_ip = "192.168.0.1"
        config = {"DataBaseConfigurations": [{
            "ass": {}
        }]}

        mock_post = mock.MagicMock(return_value=mock.MagicMock(status_code=201))
        mock_requests.post = mock_post

        setup_ml.create_database(config, auth, "ass", host_ip)

        mock_post.assert_called_with("http://" + host_ip + ":8002/manage/v2/databases",
                                     headers={"Content-Type": "application/json"}, data=json.dumps({"database-name": "ass"}),
                                     allow_redirects=True, auth=auth)

    @mock.patch("setup_ml.requests")
    def test_create_database_when_non_empty_db_config(self, mock_requests):

        auth = HTTPDigestAuth("admin", "password")
        host_ip = "192.168.0.1"
        config = {"DataBaseConfigurations": [{
            "ass": {
                "enabled" : "true"
            }
        }]}

        mock_post = mock.MagicMock(return_value=mock.MagicMock(status_code=201))
        mock_requests.post = mock_post

        setup_ml.create_database(config, auth, "ass", host_ip)

        mock_post.assert_called_with("http://" + host_ip + ":8002/manage/v2/databases",
                                     headers={"Content-Type": "application/json"}, data=json.dumps({"database-name": "ass", "enabled": "true"}),
                                     allow_redirects=True, auth=auth)

    @mock.patch("setup_ml.requests")
    def test_create_databases_when_non_empty_db_config(self, mock_requests):

        auth = HTTPDigestAuth("admin", "password")
        config = {
          "NumberOfInstancesPerZone": 2,
          "DataVolumes": [{
                "Encrypted": "false",
                "VolumeType": "gp2",
                "Iops": "10",
                "Size": "512",
                "FromSnapshot": "true",
                "SnapshotId": "snap-41163b47",
                "DeletionPolicy": "Delete",
                "Device": "/dev/sdc",
                "MountDirectory": "/var/opt/data",
                "Databases": [
                    {
                        "database-name": "ass",
                        "NumberOfforestsPerDisk": "2"
                    }
                ]
            }],
            "DataBaseConfigurations": [{
                "ass": {
                    "enabled": "true"
                }
            }]}
        permanent_ip_address_1 = "1"
        permanent_ip_address_2 = "2"
        permanent_ip_address_3 = "3"
        permanent_ip_address_4 = "4"
        permanent_ip_address_5 = "5"
        permanent_ip_address_6 = "6"
        instances = [mock.MagicMock(interfaces=[mock.MagicMock(private_ip_address="192"), mock.MagicMock(private_ip_address=permanent_ip_address_1)]),
                     mock.MagicMock(interfaces=[mock.MagicMock(private_ip_address="192"), mock.MagicMock(private_ip_address=permanent_ip_address_2)]),
                     mock.MagicMock(interfaces=[mock.MagicMock(private_ip_address="192"), mock.MagicMock(private_ip_address=permanent_ip_address_3)]),
                     mock.MagicMock(interfaces=[mock.MagicMock(private_ip_address="192"), mock.MagicMock(private_ip_address=permanent_ip_address_4)]),
                     mock.MagicMock(interfaces=[mock.MagicMock(private_ip_address="192"), mock.MagicMock(private_ip_address=permanent_ip_address_5)]),
                     mock.MagicMock(interfaces=[mock.MagicMock(private_ip_address="192"), mock.MagicMock(private_ip_address=permanent_ip_address_6)])]

        mock_post = mock.MagicMock(return_value=mock.MagicMock(status_code=201))
        mock_requests.post = mock_post

        setup_ml.create_databases(instances, config, auth)

        mock_post.assert_any_call("http://" + permanent_ip_address_1 + ":8002/manage/v2/databases",
                                     headers={"Content-Type": "application/json"}, data=json.dumps({"database-name": "ass", "enabled": "true"}),
                                     allow_redirects=True, auth=auth)

        assert_forest_was_created(mock_post, permanent_ip_address_1, "ass-forest-001-node-001", permanent_ip_address_3, "R-ass-forest-001-node-003", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_1, "ass-forest-002-node-001", permanent_ip_address_4, "R-ass-forest-002-node-004", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_2, "ass-forest-003-node-002", permanent_ip_address_4, "R-ass-forest-003-node-004", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_2, "ass-forest-004-node-002", permanent_ip_address_5, "R-ass-forest-004-node-005", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_3, "ass-forest-005-node-003", permanent_ip_address_5, "R-ass-forest-005-node-005", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_3, "ass-forest-006-node-003", permanent_ip_address_6, "R-ass-forest-006-node-006", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_4, "ass-forest-007-node-004", permanent_ip_address_6, "R-ass-forest-007-node-006", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_4, "ass-forest-008-node-004", permanent_ip_address_1, "R-ass-forest-008-node-001", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_5, "ass-forest-009-node-005", permanent_ip_address_1, "R-ass-forest-009-node-001", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_5, "ass-forest-010-node-005", permanent_ip_address_2, "R-ass-forest-010-node-002", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_6, "ass-forest-011-node-006", permanent_ip_address_2, "R-ass-forest-011-node-002", auth)
        assert_forest_was_created(mock_post, permanent_ip_address_6, "ass-forest-012-node-006", permanent_ip_address_3, "R-ass-forest-012-node-003", auth)

def assert_forest_was_created(mock_post, host_ip, forest_name, replica_host_ip, replica_forest_name, auth):
        forest_create_body = {
            "forest-name": forest_name,
            "host": host_ip,
            "database": "ass",
            "data-directory": "/var/opt/data",
            "large-data-directory": "/var/opt/data",
            "fast-data-directory": "/var/opt/data",
            "forest-replicas": {
                "forest-replica": [
                    {
                        "replica-name": replica_forest_name,
                        "host": replica_host_ip,
                        "data-directory": "/var/opt/data",
                        "large-data-directory": "/var/opt/data",
                        "fast-data-directory": "/var/opt/data",
                    }
                ]
            }
        }

        mock_post.assert_any_call("http://" + host_ip + ":8002/manage/v2/forests",
                                     headers={"Content-Type": "application/json"}, data=json.dumps(forest_create_body),
                                     allow_redirects=True, auth=auth)


if __name__ == '__main__':
    unittest.main()
