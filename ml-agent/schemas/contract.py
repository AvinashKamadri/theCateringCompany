"""
Contract data schemas
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PricingData(BaseModel):
    """Pricing information"""
    package_name: str
    base_price: float
    per_person_price: float
    estimated_total: float
    breakdown: Dict[str, float] = Field(default_factory=dict)


class UpsellItem(BaseModel):
    """Individual upsell item"""
    category: str
    name: str
    price: float
    reasoning: str
    priority: str  # high, medium, low


class UpsellsData(BaseModel):
    """Upsell recommendations"""
    upsells: List[UpsellItem]
    total_potential_revenue: float


class MarginData(BaseModel):
    """Margin calculation results"""
    total_revenue: float
    total_cost: float
    food_cost: float
    labor_cost: float
    overhead_cost: float
    gross_margin: float
    margin_percentage: float
    warnings: List[str]
    recommendations: List[str]


class StaffingData(BaseModel):
    """Staffing recommendations"""
    servers_needed: int
    bartenders_needed: int
    total_labor_hours: float
    estimated_labor_cost: float
    reasoning: str


class RiskFlag(BaseModel):
    """Risk flag"""
    type: str
    severity: str  # high, medium, low
    message: str
    recommendation: str


class MissingInfoData(BaseModel):
    """Missing information flags"""
    is_complete: bool
    missing_required: List[str]
    missing_recommended: List[str]
    risk_flags: List[RiskFlag]


class ContractData(BaseModel):
    """Complete contract data structure"""
    slots: Dict[str, Any]
    pricing: PricingData
    upsells: UpsellsData
    margin: MarginData
    staffing: StaffingData
    missing_info: MissingInfoData
    generated_at: str


class ContractOutput(BaseModel):
    """Contract output for backend"""
    contract_id: Optional[str] = None
    conversation_id: str
    project_id: str
    thread_id: str
    
    # Client information
    client_name: str
    client_phone: str
    
    # Event details
    event_type: str
    event_date: str
    service_type: str
    guest_count: int
    venue: Dict[str, Any]
    special_requests: Dict[str, Any]
    
    # Financial data
    pricing: PricingData
    upsells: UpsellsData
    margin: MarginData
    staffing: StaffingData
    
    # Metadata
    missing_info: MissingInfoData
    generated_at: str
    status: str = "draft"  # draft, sent, signed
