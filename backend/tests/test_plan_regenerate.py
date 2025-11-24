"""
Unit tests for plan regeneration
"""

import pytest

@pytest.mark.asyncio
async def test_regenerate_section():
    """Test plan section regeneration"""
    # Create a plan first
    # plan_response = client.post("/api/plans", ...)
    # plan_id = plan_response.json()["id"]
    
    # Regenerate a section
    # response = client.post(
    #     f"/api/plans/{plan_id}/section/company_overview/regenerate",
    #     headers={"Authorization": f"Bearer {token}"}
    # )
    # assert response.status_code == 200
    # assert "content" in response.json()
    # assert "sources" in response.json()
    # assert "confidence" in response.json()
    # assert "versionId" in response.json()
    pass

@pytest.mark.asyncio
async def test_regenerate_strict_json():
    """Test that regeneration returns strict JSON"""
    # response = client.post(...)
    # content = response.json()["content"]
    # # Verify content is valid and not markdown-wrapped
    # assert not content.startswith("```")
    # assert not content.startswith("```json")
    pass

