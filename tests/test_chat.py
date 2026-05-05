"""Tests for the chat endpoint."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, "src/api")

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["simulated_mode"] is True


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "JAYCO Dealer Portal API"
    assert data["mode"] == "simulated"


def test_chat_endpoint():
    response = client.post(
        "/api/chat",
        json={
            "message": "How do I repack the bearings step by step?",
            "history": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "conversation_id" in data
    assert len(data["answer"]) > 0


def test_chat_tire_wear():
    response = client.post(
        "/api/chat",
        json={
            "message": "My trailer has excessive tire wear—what could be causing this?",
            "history": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "tire wear" in data["answer"].lower() or "tire" in data["answer"].lower()
    assert len(data["citations"]) > 0


def test_chat_hub_temperature():
    response = client.post(
        "/api/chat",
        json={
            "message": "I'm noticing high hub temperature and unusual noise from the wheel",
            "history": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["answer"]) > 0


def test_chat_beam_assembly():
    response = client.post(
        "/api/chat",
        json={
            "message": "How do I identify whether I have a 7K or 8K beam assembly?",
            "history": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "7K" in data["answer"] or "8K" in data["answer"]


def test_chat_empty_message():
    response = client.post(
        "/api/chat",
        json={
            "message": "",
            "history": [],
        },
    )
    assert response.status_code == 422  # Validation error


def test_chat_with_conversation_id():
    response = client.post(
        "/api/chat",
        json={
            "message": "What maintenance should I perform on suspension?",
            "conversation_id": "test-conv-123",
            "history": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "test-conv-123"
