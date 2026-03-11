"""
Tool functionality tests
"""

import pytest
from tools.slot_validation import validate_slot
from tools.upsells import suggest_upsells
from tools.margin_calculation import calculate_margin
from tools.staffing import calculate_staffing
from tools.missing_info import flag_missing_info


def test_validate_phone():
    """Test phone validation"""
    # Valid phone
    result = validate_slot("phone", "555-123-4567")
    assert result["valid"] == True
    
    # Invalid phone
    result = validate_slot("phone", "invalid")
    assert result["valid"] == False


def test_validate_guest_count():
    """Test guest count validation"""
    # Valid count
    result = validate_slot("guest_count", 150)
    assert result["valid"] == True
    
    # Too low
    result = validate_slot("guest_count", 5)
    assert result["valid"] == False
    
    # Too high
    result = validate_slot("guest_count", 15000)
    assert result["valid"] == False


def test_validate_service_type():
    """Test service type validation"""
    # Valid types
    result = validate_slot("service_type", "on-site")
    assert result["valid"] == True
    
    result = validate_slot("service_type", "drop-off")
    assert result["valid"] == True
    
    # Invalid type
    result = validate_slot("service_type", "invalid")
    assert result["valid"] == False


@pytest.mark.asyncio
async def test_suggest_upsells_wedding():
    """Test upsell suggestions for wedding"""
    result = await suggest_upsells.ainvoke({
        "event_type": "Wedding",
        "guest_count": 150,
        "current_selections": {}
    })
    
    assert "upsells" in result
    assert len(result["upsells"]) > 0
    assert result["total_potential_revenue"] > 0
    
    # Check for wedding-specific upsells
    categories = [u["category"] for u in result["upsells"]]
    assert "Bar Service" in categories


@pytest.mark.asyncio
async def test_suggest_upsells_corporate():
    """Test upsell suggestions for corporate event"""
    result = await suggest_upsells.ainvoke({
        "event_type": "Corporate",
        "guest_count": 100,
        "current_selections": {}
    })
    
    assert "upsells" in result
    assert len(result["upsells"]) > 0
    
    # Check for corporate-specific upsells
    categories = [u["category"] for u in result["upsells"]]
    assert "Bar Service" in categories or "AV Equipment" in categories


@pytest.mark.asyncio
async def test_calculate_margin():
    """Test margin calculation"""
    line_items = [
        {"name": "Catering Package", "price": 5000.0, "cost": 3000.0}
    ]
    
    result = await calculate_margin.ainvoke({
        "line_items": line_items,
        "guest_count": 100,
        "service_type": "on-site"
    })
    
    assert result["total_revenue"] > 0
    assert result["total_cost"] > 0
    assert result["gross_margin"] > 0
    assert result["margin_percentage"] > 0
    assert "food_cost" in result
    assert "labor_cost" in result
    assert "overhead_cost" in result


@pytest.mark.asyncio
async def test_calculate_margin_low_margin_warning():
    """Test margin calculation with low margin warning"""
    line_items = [
        {"name": "Catering Package", "price": 1000.0, "cost": 900.0}
    ]
    
    result = await calculate_margin.ainvoke({
        "line_items": line_items,
        "guest_count": 50,
        "service_type": "drop-off"
    })
    
    # Should have warnings for low margin
    assert len(result["warnings"]) > 0 or result["margin_percentage"] < 30


@pytest.mark.asyncio
async def test_calculate_staffing_onsite():
    """Test staffing calculation for on-site service"""
    result = await calculate_staffing.ainvoke({
        "guest_count": 150,
        "service_type": "on-site",
        "event_type": "Wedding",
        "event_duration_hours": 6.0
    })
    
    assert result["servers_needed"] > 0
    assert result["bartenders_needed"] >= 0
    assert result["total_labor_hours"] > 0
    assert result["estimated_labor_cost"] > 0
    assert "reasoning" in result


@pytest.mark.asyncio
async def test_calculate_staffing_dropoff():
    """Test staffing calculation for drop-off service"""
    result = await calculate_staffing.ainvoke({
        "guest_count": 50,
        "service_type": "drop-off",
        "event_type": "Corporate",
        "event_duration_hours": 2.0
    })
    
    # Drop-off should require minimal staff
    assert result["servers_needed"] >= 0
    assert result["total_labor_hours"] < 10  # Should be minimal


@pytest.mark.asyncio
async def test_flag_missing_info_complete():
    """Test missing info detection with complete data"""
    slots = {
        "name": "John Smith",
        "phone": "555-123-4567",
        "event_date": "2026-06-15",
        "service_type": "on-site",
        "event_type": "Wedding",
        "venue": {"address": "123 Main St", "kitchen_access": "full", "load_in_time": "2pm"},
        "guest_count": 150,
        "special_requests": {"dietary_restrictions": ["vegetarian"], "allergies": [], "special_requests": ""}
    }
    
    result = await flag_missing_info.ainvoke({
        "slots": slots,
        "event_type": "Wedding"
    })
    
    assert "is_complete" in result
    assert result["is_complete"] == True
    assert len(result["missing_required"]) == 0


@pytest.mark.asyncio
async def test_flag_missing_info_no_kitchen_access():
    """Test missing info detection for on-site without kitchen"""
    slots = {
        "name": "John Smith",
        "phone": "555-123-4567",
        "event_date": "2026-06-15",
        "service_type": "on-site",
        "event_type": "Wedding",
        "venue": {"address": "123 Main St", "kitchen_access": "none"},
        "guest_count": 150,
        "special_requests": {}
    }
    
    result = await flag_missing_info.ainvoke({
        "slots": slots,
        "event_type": "Wedding"
    })
    
    # Should flag no kitchen access risk
    risk_types = [flag["type"] for flag in result["risk_flags"]]
    assert "no_kitchen_access" in risk_types


@pytest.mark.asyncio
async def test_flag_missing_info_large_event():
    """Test missing info detection for large event"""
    slots = {
        "name": "John Smith",
        "phone": "555-123-4567",
        "event_date": "2026-06-15",
        "service_type": "on-site",
        "event_type": "Corporate",
        "venue": {"address": "123 Main St", "kitchen_access": "full"},
        "guest_count": 350,  # Large event
        "special_requests": {}
    }
    
    result = await flag_missing_info.ainvoke({
        "slots": slots,
        "event_type": "Corporate"
    })
    
    # Should flag large event risk
    risk_types = [flag["type"] for flag in result["risk_flags"]]
    assert "large_event" in risk_types


@pytest.mark.asyncio
async def test_flag_missing_info_severe_allergies():
    """Test missing info detection for severe allergies"""
    slots = {
        "name": "John Smith",
        "phone": "555-123-4567",
        "event_date": "2026-06-15",
        "service_type": "on-site",
        "event_type": "Wedding",
        "venue": {"address": "123 Main St", "kitchen_access": "full"},
        "guest_count": 150,
        "special_requests": {"allergies": ["peanut", "shellfish"]}
    }
    
    result = await flag_missing_info.ainvoke({
        "slots": slots,
        "event_type": "Wedding"
    })
    
    # Should flag severe allergies
    risk_types = [flag["type"] for flag in result["risk_flags"]]
    assert "severe_allergies" in risk_types
