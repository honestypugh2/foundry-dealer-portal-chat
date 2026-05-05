"""Tests for the search endpoint."""

import sys
sys.path.insert(0, "src/api")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_search_bearings():
    response = client.post(
        "/api/search",
        json={"query": "bearing repack procedure", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] > 0
    assert any("bearing" in r["chunk_text"].lower() for r in data["results"])


def test_search_tire_wear():
    response = client.post(
        "/api/search",
        json={"query": "tire wear causes", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] > 0


def test_search_with_source_filter():
    response = client.post(
        "/api/search",
        json={"query": "torque specifications", "top_k": 5, "source_filter": "SharePoint"},
    )
    assert response.status_code == 200
    data = response.json()
    for result in data["results"]:
        assert result["source_system"] == "SharePoint"


def test_search_no_results():
    response = client.post(
        "/api/search",
        json={"query": "xyznonexistentquery123", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0


def test_documents_list_all():
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 9
    sources = set(d["source_system"] for d in data["documents"])
    assert "SharePoint" in sources
    assert "Revver" in sources


def test_documents_list_sharepoint():
    response = client.get("/api/documents?source=sharepoint")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 5
    for doc in data["documents"]:
        assert doc["source_system"] == "SharePoint"


def test_documents_list_revver():
    response = client.get("/api/documents?source=revver")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 4
    for doc in data["documents"]:
        assert doc["source_system"] == "Revver"
