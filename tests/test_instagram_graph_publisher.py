import pytest
from unittest.mock import MagicMock, patch
from src.publishers.instagram.official_publisher import InstagramGraphPublisherClient
from src.pipeline import Pipeline
from src.models import Product

def test_login_simulated():
    client = InstagramGraphPublisherClient(
        business_account_id="12345",
        access_token="token_abc",
        simulate=True
    )
    assert client.login() is True
    assert client.is_logged_in is True

@patch("src.publishers.instagram.official_publisher.requests.get")
def test_login_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "12345", "username": "grabhive_official"}
    mock_get.return_value = mock_resp

    client = InstagramGraphPublisherClient(
        business_account_id="12345",
        access_token="token_abc",
        simulate=False
    )
    assert client.login() is True
    assert client.is_logged_in is True
    mock_get.assert_called_once()

@patch("src.publishers.instagram.official_publisher.requests.get")
def test_login_failure_warns_but_proceeds(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "Invalid OAuth access token."
    mock_get.return_value = mock_resp

    client = InstagramGraphPublisherClient(
        business_account_id="12345",
        access_token="invalid_token",
        simulate=False
    )
    # With the fallback, login should succeed (return True) even if API check fails
    assert client.login() is True
    assert client.is_logged_in is True

def test_login_missing_credentials():
    client = InstagramGraphPublisherClient(
        business_account_id="",
        access_token="",
        simulate=False
    )
    assert client.login() is False
    assert client.is_logged_in is False

def test_publish_simulated():
    client = InstagramGraphPublisherClient(
        business_account_id="12345",
        access_token="token_abc",
        simulate=True
    )
    res = client.publish("https://example.com/image.jpg", "Test Caption")
    assert res == "17983683849042983_graph_simulated"

@patch("src.publishers.instagram.official_publisher.requests.post")
@patch("src.publishers.instagram.official_publisher.requests.get")
def test_publish_live_flow_success(mock_get, mock_post):
    # Mock login get response
    mock_login_resp = MagicMock()
    mock_login_resp.status_code = 200
    mock_login_resp.json.return_value = {"id": "12345", "username": "grabhive"}
    
    # Mock container status get response
    mock_status_resp = MagicMock()
    mock_status_resp.status_code = 200
    mock_status_resp.json.return_value = {"status_code": "FINISHED"}
    
    mock_get.side_effect = [mock_login_resp, mock_status_resp]

    # Mock container creation post response
    mock_container_resp = MagicMock()
    mock_container_resp.status_code = 200
    mock_container_resp.json.return_value = {"id": "container_999"}

    # Mock publish post response
    mock_publish_resp = MagicMock()
    mock_publish_resp.status_code = 200
    mock_publish_resp.json.return_value = {"id": "media_77777"}

    mock_post.side_effect = [mock_container_resp, mock_publish_resp]

    client = InstagramGraphPublisherClient(
        business_account_id="12345",
        access_token="token_abc",
        simulate=False
    )
    
    res = client.publish("temp/local.jpg", "Caption text", image_url="https://images.example.com/item.jpg")
    
    assert res == "media_77777"
    assert mock_post.call_count == 2
    assert mock_get.call_count == 2

@patch("src.publishers.instagram.official_publisher.requests.post")
@patch("src.publishers.instagram.official_publisher.requests.get")
def test_publish_rate_limit_fallback(mock_get, mock_post):
    mock_login_resp = MagicMock()
    mock_login_resp.status_code = 200
    mock_login_resp.json.return_value = {"id": "12345", "username": "grabhive"}
    
    mock_status_resp = MagicMock()
    mock_status_resp.status_code = 200
    mock_status_resp.json.return_value = {"status_code": "FINISHED"}
    
    mock_get.side_effect = [mock_login_resp, mock_status_resp]

    mock_container_resp = MagicMock()
    mock_container_resp.status_code = 200
    mock_container_resp.json.return_value = {"id": "container_999"}

    # Mock 403 rate limit / action blocked response
    mock_publish_resp = MagicMock()
    mock_publish_resp.status_code = 403
    mock_publish_resp.text = '{"error":{"message":"Application request limit reached","type":"OAuthException","code":4,"error_subcode":2207051}}'
    mock_publish_resp.json.return_value = {
        "error": {
            "message": "Application request limit reached",
            "type": "OAuthException",
            "code": 4,
            "error_subcode": 2207051
        }
    }

    mock_post.side_effect = [mock_container_resp, mock_publish_resp]

    client = InstagramGraphPublisherClient(
        business_account_id="12345",
        access_token="token_abc",
        simulate=False
    )
    
    res = client.publish("temp/local.jpg", "Caption text", image_url="https://images.example.com/item.jpg")
    
    assert res == "container_999"
    assert mock_post.call_count == 2

def test_publish_no_public_url_fails():
    client = InstagramGraphPublisherClient(
        business_account_id="12345",
        access_token="token_abc",
        simulate=False
    )
    client.is_logged_in = True
    
    # Pass local path and no HTTP URL for image_url
    res = client.publish("temp/local.jpg", "Caption text", image_url=None)
    assert res is None

def test_pipeline_whatsapp_unaffected_with_graph_api(tmp_path):
    mock_sheet = MagicMock()
    mock_image_gen = MagicMock()
    mock_insta_pub = MagicMock()
    mock_whatsapp_pub = MagicMock()

    product = Product(
        row_index=2,
        name="Test Product",
        affiliate_link="https://amzn.to/example",
        image_url="https://m.media-amazon.com/images/I/71.jpg",
        rating="4.5",
        price="₹999",
        provider="Amazon",
        insta_flag="N",
        whatsapp_flag="N"
    )
    mock_sheet.get_pending_product.return_value = product
    mock_image_gen.download_image.return_value = "temp/downloaded.jpg"
    mock_insta_pub.publish.return_value = "graph_post_12345"
    mock_whatsapp_pub.send_message.return_value = True

    progress_file = tmp_path / "progress.json"
    pipeline = Pipeline(
        sheet_client=mock_sheet,
        image_gen=mock_image_gen,
        insta_pub=mock_insta_pub,
        whatsapp_pub=mock_whatsapp_pub,
        progress_path=str(progress_file)
    )

    processed = pipeline.run_once()

    assert processed is True
    # Verify Instagram publisher was called with image_url
    mock_insta_pub.publish.assert_called_once_with(
        "temp/downloaded.jpg", 
        pipeline.insta_pub.publish.call_args[0][1], 
        image_url="https://m.media-amazon.com/images/I/71.jpg"
    )
    # Verify WhatsApp send_message was called and succeeded without modification
    mock_whatsapp_pub.send_message.assert_called()
    mock_sheet.mark_product_completed.assert_called_once()

@patch("src.scheduler.GoogleSheetClient")
@patch("src.scheduler.PILImageGenerator")
@patch("src.scheduler.WhatsAppPublisherClient")
@patch("src.scheduler.Pipeline")
def test_scheduler_publisher_selection_official(mock_pipeline, mock_wa, mock_img, mock_sheet):
    with patch("src.scheduler.INSTAGRAM_USE_OFFICIAL_API", True), \
         patch("src.scheduler.InstagramGraphPublisherClient") as mock_graph_client, \
         patch("src.scheduler.InstagramPublisherClient") as mock_unoff_client:
        from src.scheduler import run_pipeline
        run_pipeline()
        mock_graph_client.assert_called_once()
        mock_unoff_client.assert_not_called()

@patch("src.scheduler.GoogleSheetClient")
@patch("src.scheduler.PILImageGenerator")
@patch("src.scheduler.WhatsAppPublisherClient")
@patch("src.scheduler.Pipeline")
def test_scheduler_publisher_selection_unofficial(mock_pipeline, mock_wa, mock_img, mock_sheet):
    with patch("src.scheduler.INSTAGRAM_USE_OFFICIAL_API", False), \
         patch("src.scheduler.InstagramGraphPublisherClient") as mock_graph_client, \
         patch("src.scheduler.InstagramPublisherClient") as mock_unoff_client:
        from src.scheduler import run_pipeline
        run_pipeline()
        mock_unoff_client.assert_called_once()
        mock_graph_client.assert_not_called()

