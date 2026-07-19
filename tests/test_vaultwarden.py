import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.services.vaultwarden import (
    BitwardenDaemon,
    get_folders,
    get_existing_ssh_keys,
    get_item_by_name,
    create_ssh_key_item,
    create_secure_note_item,
    create_secure_login,
    get_ssh_key_item
)

@pytest.fixture
def mock_daemon_ready():
    with patch.object(BitwardenDaemon, "ensure_ready") as mock_ready:
        yield mock_ready

def test_daemon_status():
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "success": True,
        "data": {
            "template": {
                "status": "unlocked"
            }
        }
    }
    
    with patch.object(BitwardenDaemon, "is_running", return_value=True), \
         patch("httpx.get", return_value=mock_res) as mock_get:
        status = BitwardenDaemon.get_status()
        assert status == "unlocked"
        mock_get.assert_called_once_with("http://127.0.0.1:8087/status", timeout=2.0)

def test_daemon_unlock():
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "success": True,
        "data": {
            "raw": "mock-session-key"
        }
    }
    
    with patch.object(BitwardenDaemon, "start"), \
         patch("httpx.post", return_value=mock_res) as mock_post, \
         patch("app.services.vaultwarden.set_secret") as mock_set_secret:
        success = BitwardenDaemon.unlock("mock-password")
        assert success is True
        mock_set_secret.assert_called_once_with("BW_SESSION", "mock-session-key")
        mock_post.assert_called_once_with(
            "http://127.0.0.1:8087/unlock",
            json={"password": "mock-password"},
            timeout=10.0
        )

def test_get_folders(mock_daemon_ready):
    mock_sync_res = MagicMock()
    mock_sync_res.status_code = 200
    
    mock_folders_res = MagicMock()
    mock_folders_res.status_code = 200
    mock_folders_res.json.return_value = {
        "success": True,
        "data": {
            "data": [
                {"name": "FolderA", "id": "id-a"},
                {"name": "FolderB", "id": "id-b"}
            ]
        }
    }
    
    with patch("httpx.post", return_value=mock_sync_res), \
         patch("httpx.get", return_value=mock_folders_res):
        folders = get_folders()
        assert len(folders) == 2
        assert folders[0]["name"] == "FolderA"
        assert folders[1]["id"] == "id-b"

def test_get_existing_ssh_keys(mock_daemon_ready):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "success": True,
        "data": {
            "data": [
                {"name": "key-1", "type": 5},
                {"name": "login-1", "type": 1},
                {"name": "key-2", "type": 5}
            ]
        }
    }
    
    with patch("httpx.get", return_value=mock_res):
        keys = get_existing_ssh_keys()
        assert keys == ["key-1", "key-2"]

def test_get_item_by_name(mock_daemon_ready):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "success": True,
        "data": {
            "data": [
                {"name": "my-item", "id": "item-id-123", "type": 5}
            ]
        }
    }
    
    with patch("httpx.get", return_value=mock_res) as mock_get:
        item_id = get_item_by_name("my-item", item_type=5)
        assert item_id == "item-id-123"
        mock_get.assert_called_once_with(
            "http://127.0.0.1:8087/list/object/items",
            params={"search": "my-item"},
            timeout=10.0
        )

def test_create_ssh_key_item_new(mock_daemon_ready):
    # Mock template response
    mock_temp_res = MagicMock()
    mock_temp_res.status_code = 200
    mock_temp_res.json.return_value = {
        "success": True,
        "data": {
            "template": {
                "name": "",
                "type": 1,
                "sshKey": None
            }
        }
    }
    
    # Mock post response
    mock_post_res = MagicMock()
    mock_post_res.status_code = 200
    mock_post_res.json.return_value = {
        "success": True,
        "data": {"id": "new-ssh-id", "name": "new-ssh-key"}
    }
    
    def side_effect_get(url, *args, **kwargs):
        if "/object/template/item" in url:
            return mock_temp_res
        return MagicMock(status_code=404)
        
    with patch("httpx.get", side_effect=side_effect_get), \
         patch("httpx.post", return_value=mock_post_res) as mock_post:
        res = create_ssh_key_item(
            name="new-ssh-key",
            private_key="priv",
            public_key="pub",
            fingerprint="fp",
            folder_id="folder-123"
        )
        assert res["id"] == "new-ssh-id"
        assert res["name"] == "new-ssh-key"
        mock_post.assert_called_once()

def test_create_ssh_key_item_edit(mock_daemon_ready):
    # Mock get item response
    mock_get_res = MagicMock()
    mock_get_res.status_code = 200
    mock_get_res.json.return_value = {
        "success": True,
        "data": {
            "id": "existing-id",
            "name": "old-name",
            "type": 5,
            "fields": []
        }
    }
    
    # Mock put response
    mock_put_res = MagicMock()
    mock_put_res.status_code = 200
    mock_put_res.json.return_value = {
        "success": True,
        "data": {"id": "existing-id", "name": "updated-name"}
    }
    
    with patch("httpx.get", return_value=mock_get_res), \
         patch("httpx.put", return_value=mock_put_res) as mock_put:
        res = create_ssh_key_item(
            name="updated-name",
            private_key="priv",
            public_key="pub",
            fingerprint="fp",
            item_id="existing-id"
        )
        assert res["name"] == "updated-name"
        mock_put.assert_called_once()
