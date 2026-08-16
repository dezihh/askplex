# -*- coding: utf-8 -*-
"""
Tests für den DynamoDB-Pfad des QueueStore.

boto3 wird gemockt; es wird keine echte DynamoDB-Tabelle benötigt.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from askplex.ams_controller import QueueStore


@pytest.fixture
def store():
    return QueueStore(logging.getLogger("test-store"))


@pytest.fixture
def mock_table():
    table = MagicMock()
    fake_resource = MagicMock()
    fake_resource.Table.return_value = table

    with patch.dict(os.environ, {"AMS_QUEUE_STORE": "dynamodb"}), \
            patch("boto3.resource", return_value=fake_resource):
        yield table


class TestQueueStoreDynamoDb:
    def test_save_writes_item_with_ttl(self, store, mock_table):
        store.save("queue-1", {"contentId": "plex:artist:42", "tracks": []})

        _, kwargs = mock_table.put_item.call_args
        item = kwargs["Item"]
        assert item["queueId"] == "queue-1"
        assert item["contentId"] == "plex:artist:42"
        assert item["expiresAt"] > 0

    def test_load_reads_item(self, store, mock_table):
        mock_table.get_item.return_value = {"Item": {"queueId": "queue-1", "tracks": []}}
        result = store.load("queue-1")

        mock_table.get_item.assert_called_once_with(Key={"queueId": "queue-1"})
        assert result == {"queueId": "queue-1", "tracks": []}

    def test_load_missing_item_returns_none(self, store, mock_table):
        mock_table.get_item.return_value = {}
        assert store.load("queue-1") is None

    def test_load_none_returns_none_without_ddb_call(self, store, mock_table):
        assert store.load(None) is None
        mock_table.get_item.assert_not_called()

    def test_save_error_is_logged_not_raised(self, store, mock_table):
        mock_table.put_item.side_effect = Exception("boom")
        store.save("queue-1", {})
        mock_table.put_item.assert_called_once()

    def test_load_error_returns_none(self, store, mock_table):
        mock_table.get_item.side_effect = Exception("boom")
        assert store.load("queue-1") is None
