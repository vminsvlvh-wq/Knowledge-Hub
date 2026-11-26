def test_application_module_imports():
    from app.main import app

    assert app.title == "Knowledge Intelligence"
    assert any(route.path == "/api/v1/tenants" for route in app.routes)
