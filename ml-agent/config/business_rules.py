"""
Business rules and configuration for the catering AI agent.
All hardcoded business logic is centralized here for easy maintenance.
"""

from typing import Dict, Any
from decimal import Decimal


class BusinessConfig:
    """Centralized business configuration for catering operations."""
    
    # ============================================================================
    # PRICING & FINANCIAL RULES
    # ============================================================================
    
    # Tax and fees
    TAX_RATE = 0.094  # 9.4% sales tax
    GRATUITY_RATE = 0.20  # 20% service & gratuity
    DEPOSIT_PERCENTAGE = 0.50  # 50% deposit required
    
    # Payment processing fees
    CREDIT_CARD_FEE = 0.05  # 5% for credit/debit cards
    VENMO_FEE = 0.02  # 2% for Venmo
    
    # ============================================================================
    # STAFFING RULES
    # ============================================================================
    
    # Staff-to-guest ratios
    GUESTS_PER_SERVER = 20  # 1 server per 20 guests
    GUESTS_PER_BARTENDER = 75  # 1 bartender per 75 guests
    MIN_SERVERS = 2  # Minimum servers for any on-site event
    MIN_BARTENDERS = 1  # Minimum bartenders for any on-site event
    
    # Labor rates (per hour)
    SERVER_HOURLY_RATE = 25.00
    BARTENDER_HOURLY_RATE = 30.00
    SUPERVISOR_HOURLY_RATE = 50.00
    DELIVERY_STAFF_HOURLY_RATE = 25.00
    
    # Event duration assumptions
    DEFAULT_EVENT_DURATION_HOURS = 6.0
    DROPOFF_DELIVERY_HOURS = 1.0
    MIN_DELIVERY_STAFF = 2
    
    # Additional labor charges (for events exceeding standard duration)
    ADDITIONAL_SERVER_RATE = 30.00  # per hour
    ADDITIONAL_SUPERVISOR_RATE = 50.00  # per hour
    OVERTIME_THRESHOLD_HOURS = 6.0
    
    # ============================================================================
    # MARGIN & COST RULES
    # ============================================================================
    
    # Cost percentages (as fraction of revenue)
    FOOD_COST_PERCENTAGE = 0.32  # 32% of revenue
    OVERHEAD_PERCENTAGE = 0.18  # 18% of revenue (rent, utilities, admin)
    
    # Margin thresholds
    MARGIN_CRITICAL_THRESHOLD = 20.0  # Below this is critical
    MARGIN_WARNING_THRESHOLD = 30.0  # Below this is warning
    MARGIN_EXCELLENT_THRESHOLD = 40.0  # Above this is excellent
    
    # ============================================================================
    # SERVICE TYPE
    # ============================================================================

    VALID_SERVICE_TYPES = ["Drop-off", "Onsite"]

    # ============================================================================
    # PRICING PACKAGE SELECTION RULES
    # ============================================================================

    # Guest count threshold for package selection
    PREMIUM_PACKAGE_GUEST_THRESHOLD = 75  # Above this, select higher-tier packages

    # ============================================================================
    # BAR SERVICE PRICING
    # ============================================================================

    BARTENDER_RATE = 50.00       # per hour
    BARTENDER_MIN_HOURS = 5      # minimum 5-hour booking

    BAR_PACKAGES = {
        "beer_wine": {
            "label": "Beer & Wine",
            "description": "Selection of domestic/imported beers and house wines",
            "price_pp": 15.00,
        },
        "beer_wine_signatures": {
            "label": "Beer, Wine & Signature Cocktails",
            "description": "Beer & wine plus 2 signature cocktails of your choice",
            "price_pp": 22.00,
        },
        "full_open_bar": {
            "label": "Full Open Bar",
            "description": "Full liquor, beer, wine, and mixers",
            "price_pp": 30.00,
        },
    }

    # ============================================================================
    # TABLEWARE
    # ============================================================================

    PREMIUM_DISPOSABLE_PP = 1.00   # gold/silver upgrade per person

    # China staffing tiers (guest count → staffing cost)
    CHINA_STAFFING = {
        50: 175,
        75: 250,
        100: 325,
        125: 425,
        150: 550,
    }

    # ============================================================================
    # LABOR SERVICES
    # ============================================================================

    # Setup
    CEREMONY_SETUP_PP = 1.50
    TABLE_CHAIR_SETUP_PP = 2.00
    TABLE_PRESET_PP = 1.75

    # Cleanup
    RECEPTION_CLEANUP_PP = 3.75
    TRASH_REMOVAL_FLAT = 175

    # Travel fees
    TRAVEL_FEES = {
        "30_min": 150,
        "1_hour": 250,
        "extended": 375,
    }

    # ============================================================================
    # GRATUITY & SERVICE FEES
    # ============================================================================

    GRATUITY_STANDARD = 0.15       # 15% standard gratuity
    GRATUITY_CHINA_STATION = 0.18  # 18% for china / station service
    ONSITE_SERVICE_FEE = 0.065     # 6.5% onsite service fee

    # ============================================================================
    # ADD-ON PRICING (fallback estimates when not in DB)
    # ============================================================================

    # Rentals (per unit)
    RENTAL_RATES = {
        "linens": 8.00,
        "tables": 15.00,
        "chairs": 5.00,
    }

    # Rental quantity calculations
    GUESTS_PER_TABLE = 8
    CHAIRS_PER_GUEST = 1
    LINENS_PER_TABLE = 1
    
    # ============================================================================
    # CANCELLATION & REFUND POLICY
    # ============================================================================
    
    CANCELLATION_POLICY = {
        "over_60_days": {
            "description": "Over 60 days before event",
            "penalty": "$500 date freeze forfeited",
            "refund_percentage": None,
        },
        "30_to_60_days": {
            "description": "30-60 days before event",
            "penalty": "$500 forfeited",
            "refund_percentage": 0.30,  # Max 30% deposit refund
        },
        "under_30_days": {
            "description": "Under 30 days before event",
            "penalty": "Deposit forfeited",
            "refund_percentage": 0.0,
        },
        "under_14_days": {
            "description": "Under 2 weeks before event",
            "penalty": "100% forfeited",
            "refund_percentage": 0.0,
        },
    }
    
    # ============================================================================
    # GUEST COUNT VARIANCE POLICY
    # ============================================================================
    
    GUEST_COUNT_VARIANCE_THRESHOLD = 0.10  # 10% drop triggers price adjustment
    
    # ============================================================================
    # CONTACT & COMPANY INFO
    # ============================================================================
    
    COMPANY_NAME = "The Catering Company"
    COMPANY_LEGAL_NAME = "The Caterer, LLC"
    COMPANY_EMAIL = "info@thecatering-company.com"
    COMPANY_PHONE = "540-458-1808"
    
    # ============================================================================
    # CONTRACT GENERATION RULES
    # ============================================================================
    
    CONTRACT_PREFIX = "CC"  # Contract number prefix
    CONTRACT_BALANCE_DUE_DAYS = 21  # Balance due 3 weeks (21 days) before event
    
    CONTRACT_FOOTER_NOTES = [
        "Disposable Service Included",
        "9.4% Tax and 20% Service and Gratuity Charge on all events",
    ]
    
    # ============================================================================
    # VALIDATION RULES
    # ============================================================================
    
    # Phone validation
    DEFAULT_COUNTRY_CODE = "+1"  # US country code
    PHONE_MIN_LENGTH = 10
    
    # Guest count limits
    MIN_GUEST_COUNT = 1
    MAX_GUEST_COUNT = 1000
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    @classmethod
    def calculate_service_surcharge(cls, guest_count: int, service_type: str) -> float:
        """Calculate service surcharge for on-site events."""
        if not service_type or "onsite" not in service_type.lower():
            return 0.0
        
        servers = max(cls.MIN_SERVERS, (guest_count // cls.GUESTS_PER_SERVER) + 1)
        bartenders = max(cls.MIN_BARTENDERS, guest_count // cls.GUESTS_PER_BARTENDER)
        
        server_cost = servers * cls.DEFAULT_EVENT_DURATION_HOURS * cls.SERVER_HOURLY_RATE
        bartender_cost = bartenders * cls.DEFAULT_EVENT_DURATION_HOURS * cls.BARTENDER_HOURLY_RATE
        
        return server_cost + bartender_cost
    
    @classmethod
    def calculate_dropoff_labor_cost(cls) -> float:
        """Calculate labor cost for drop-off delivery."""
        return cls.MIN_DELIVERY_STAFF * cls.DROPOFF_DELIVERY_HOURS * cls.DELIVERY_STAFF_HOURLY_RATE
    
    @classmethod
    def get_rental_quantity(cls, rental_type: str, guest_count: int) -> int:
        """Calculate rental quantity based on guest count."""
        if rental_type == "tables":
            return max(1, guest_count // cls.GUESTS_PER_TABLE)
        elif rental_type == "chairs":
            return guest_count * cls.CHAIRS_PER_GUEST
        elif rental_type == "linens":
            return max(1, guest_count // cls.GUESTS_PER_TABLE)
        return 1
    
    @classmethod
    def get_margin_status(cls, margin_percentage: float) -> Dict[str, Any]:
        """Determine margin status and generate warnings/recommendations."""
        warnings = []
        recommendations = []
        status = "good"
        
        if margin_percentage < cls.MARGIN_CRITICAL_THRESHOLD:
            status = "critical"
            warnings.append(
                f"CRITICAL: Margin is only {margin_percentage:.1f}% - "
                f"below minimum threshold of {cls.MARGIN_CRITICAL_THRESHOLD}%"
            )
            recommendations.append("Consider increasing pricing or reducing costs")
            recommendations.append("Review food costs and portion sizes")
        elif margin_percentage < cls.MARGIN_WARNING_THRESHOLD:
            status = "warning"
            warnings.append(
                f"WARNING: Margin is {margin_percentage:.1f}% - "
                f"below target of {cls.MARGIN_WARNING_THRESHOLD}%"
            )
            recommendations.append("Look for opportunities to optimize costs")
        elif margin_percentage >= cls.MARGIN_EXCELLENT_THRESHOLD:
            status = "excellent"
            recommendations.append(
                f"Excellent margin of {margin_percentage:.1f}% - well above target"
            )
        
        return {
            "status": status,
            "warnings": warnings,
            "recommendations": recommendations,
        }
    
    @classmethod
    def format_cancellation_policy(cls) -> str:
        """Format cancellation policy for contract."""
        lines = []
        for key, policy in cls.CANCELLATION_POLICY.items():
            if policy["refund_percentage"] is not None:
                refund_text = f"max {int(policy['refund_percentage'] * 100)}% deposit refund"
            else:
                refund_text = ""
            
            penalty = policy["penalty"]
            if refund_text:
                lines.append(f"{policy['description']}: {refund_text} minus {penalty}")
            else:
                lines.append(f"{policy['description']}: {penalty}")
        
        return "; ".join(lines)
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Export all configuration as a dictionary."""
        return {
            "tax_rate": cls.TAX_RATE,
            "gratuity_rate": cls.GRATUITY_RATE,
            "deposit_percentage": cls.DEPOSIT_PERCENTAGE,
            "credit_card_fee": cls.CREDIT_CARD_FEE,
            "venmo_fee": cls.VENMO_FEE,
            "guests_per_server": cls.GUESTS_PER_SERVER,
            "guests_per_bartender": cls.GUESTS_PER_BARTENDER,
            "server_hourly_rate": cls.SERVER_HOURLY_RATE,
            "bartender_hourly_rate": cls.BARTENDER_HOURLY_RATE,
            "food_cost_percentage": cls.FOOD_COST_PERCENTAGE,
            "overhead_percentage": cls.OVERHEAD_PERCENTAGE,
            "company_name": cls.COMPANY_NAME,
            "company_email": cls.COMPANY_EMAIL,
            "company_phone": cls.COMPANY_PHONE,
        }


# Singleton instance for easy import
config = BusinessConfig()
