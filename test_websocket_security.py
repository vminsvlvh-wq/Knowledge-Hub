from app.collaboration import is_allowed_websocket_origin


def test_websocket_allows_same_origin():
    assert is_allowed_websocket_origin("https://ki.example.com", "ki.example.com", [])


def test_websocket_allows_explicit_configured_origin():
    assert is_allowed_websocket_origin(
        "https://frontend.example.com", "api.example.com",
        ["https://frontend.example.com"],
    )


def test_websocket_rejects_untrusted_or_malformed_origin():
    assert not is_allowed_websocket_origin("https://evil.example", "ki.example.com", [])
    assert not is_allowed_websocket_origin("javascript://ki.example.com", "ki.example.com", [])
    assert not is_allowed_websocket_origin("", "ki.example.com", [])
