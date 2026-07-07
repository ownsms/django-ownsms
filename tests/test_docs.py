import pytest
from django.test import Client


@pytest.mark.django_db
def test_openapi_schema_served():
    r = Client().get("/api/v1/openapi.yaml")
    assert r.status_code == 200
    body = r.content.decode()
    assert "openapi:" in body and "ownsms" in body


@pytest.mark.django_db
def test_swagger_ui_page():
    r = Client().get("/api/v1/docs")
    assert r.status_code == 200
    html = r.content.decode()
    assert "swagger-ui" in html
    assert "/api/v1/openapi.yaml" in html  # points at the schema
