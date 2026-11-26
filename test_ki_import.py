def test_application_module_imports():
    from app.main import app

    assert app.title == "Knowledge Intelligence"
    assert "/api/v1/tenants" in app.openapi()["paths"]
