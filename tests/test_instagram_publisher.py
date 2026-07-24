import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from instagrapi.exceptions import LoginRequired, PhotoNotUpload
from src.instagram.publisher import InstagramPublisherClient

@patch("src.instagram.publisher.Client")
def test_login_session_restored_successfully(mock_client_class, tmp_path):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Mock settings file
    session_file = tmp_path / "instagram_session.json"
    session_file.write_text("dummy session content")
    
    with patch("src.instagram.publisher.SESSION_FILE", session_file):
        publisher = InstagramPublisherClient(username="test_user", password="test_password", simulate=False)
        
        # When get_timeline_feed succeeds, session is valid
        mock_client.get_timeline_feed.return_value = {}
        
        logged_in = publisher.login()
        
        assert logged_in is True
        assert publisher.is_logged_in is True
        mock_client.load_settings.assert_called_once_with(session_file)
        mock_client.login.assert_not_called()
        mock_client.get_timeline_feed.assert_called_once()
        # Should not delete the session file
        assert session_file.exists()

@patch("src.instagram.publisher.Client")
def test_login_session_expired_falls_back_to_fresh_login(mock_client_class, tmp_path):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Mock settings file
    session_file = tmp_path / "instagram_session.json"
    session_file.write_text("dummy session content")
    
    with patch("src.instagram.publisher.SESSION_FILE", session_file):
        publisher = InstagramPublisherClient(username="test_user", password="test_password", simulate=False)
        
        # When get_timeline_feed fails with LoginRequired
        mock_client.get_timeline_feed.side_effect = LoginRequired("login required")
        
        logged_in = publisher.login()
        
        assert logged_in is True
        assert publisher.is_logged_in is True
        mock_client.load_settings.assert_called_once_with(session_file)
        # Should have tried to log in once for fresh login
        assert mock_client.login.call_count == 1
        # The session file should have been deleted and recreated
        mock_client.dump_settings.assert_called_once_with(session_file)

@patch("src.instagram.publisher.Client")
def test_publish_retry_on_login_required(mock_client_class, tmp_path):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    session_file = tmp_path / "instagram_session.json"
    session_file.write_text("dummy session content")
    
    with patch("src.instagram.publisher.SESSION_FILE", session_file):
        publisher = InstagramPublisherClient(username="test_user", password="test_password", simulate=False)
        publisher.cl = mock_client
        publisher.is_logged_in = True
        
        # Mock photo_upload: first fails with PhotoNotUpload containing 'login_required', second succeeds
        mock_media = MagicMock()
        mock_media.id = "12345_media"
        mock_media.pk = "12345"
        mock_client.photo_upload.side_effect = [
            PhotoNotUpload('{"message":"login_required","status":"fail"}'),
            mock_media
        ]
        
        # Mock private_request for FBID
        mock_client.private_request.return_value = {"items": [{"fbid": 987654321}]}
        
        media_id = publisher.publish("dummy_path.jpg", "caption")
        
        assert media_id == "987654321"
        assert mock_client.photo_upload.call_count == 2
        # Verify it triggered a session deletion and login flow
        assert not session_file.exists()
