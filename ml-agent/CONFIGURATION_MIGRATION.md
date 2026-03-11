# Configuration System Migration Guide

## Overview

The catering AI agent has been updated to use a centralized configuration system. All hardcoded business values have been moved to `config/business_rules.py` for better maintainability.

## What Changed

### Before (Hardcoded Values)
```python
# In tools/pricing.py
TAX_RATE = 0.094       # 9.4% tax
GRATUITY_RATE = 0.20   # 20% service & gratuity

# In tools/margin_calculation.py
food_cost_percentage = 0.32
overhead_percentage = 0.18

# In agent/nodes/final.py
contract_number = f"CC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
```

### After (Centralized Configuration)
```python
# Import configuration
from config.business_rules import config

# Use configuration values
tax = subtotal * config.TAX_RATE
gratuity = subtotal * config.GRATUITY_RATE
food_cost = revenue * config.FOOD_COST_PERCENTAGE
contract_number = f"{config.CONTRACT_PREFIX}-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
```

## Files Updated

### 1. `tools/pricing.py`
- ✅ Tax and gratuity rates now use `config.TAX_RATE` and `config.GRATUITY_RATE`
- ✅ Service surcharge calculation moved to `config.calculate_service_surcharge()`
- ✅ Rental rates and quantities use `config.RENTAL_RATES` and `config.get_rental_quantity()`
- ✅ Utensil pricing uses `config.UTENSIL_PACKAGE_PER_PERSON`

### 2. `tools/margin_calculation.py`
- ✅ Food cost percentage uses `config.FOOD_COST_PERCENTAGE`
- ✅ Overhead percentage uses `config.OVERHEAD_PERCENTAGE`
- ✅ Staffing calculations use config values
- ✅ Margin thresholds use `config.get_margin_status()`

### 3. `tools/staffing.py`
- ✅ Implemented full staffing calculation (was TODO)
- ✅ Uses config for all staffing ratios and rates
- ✅ Supports both on-site and drop-off service types

### 4. `agent/nodes/final.py`
- ✅ Contract generation uses config for all policies
- ✅ Billing summary uses dynamic tax/gratuity rates
- ✅ Company information from config
- ✅ Cancellation policy formatting

### 5. `tools/slot_validation.py`
- ✅ Phone validation uses `config.DEFAULT_COUNTRY_CODE`

## New Configuration Features

### 1. Centralized Business Rules (`config/business_rules.py`)
All business logic in one place:
- Tax rates and fees
- Staffing ratios and labor rates
- Margin thresholds
- Pricing rules
- Company information
- Policies and terms

### 2. Configuration Management (`config/config_manager.py`)
Tools for managing configuration:
- Validation of configuration values
- Export to JSON, YAML, or environment variables
- Configuration comparison
- Summary reporting

### 3. Helper Methods
Smart calculation methods:
- `calculate_service_surcharge()` - On-site service costs
- `calculate_dropoff_labor_cost()` - Delivery costs
- `get_rental_quantity()` - Rental calculations
- `get_margin_status()` - Margin analysis
- `format_cancellation_policy()` - Policy formatting

## Benefits

### 1. Maintainability
- All business rules in one file
- Easy to update rates and policies
- No more hunting through code for hardcoded values

### 2. Consistency
- Same values used throughout the application
- Eliminates discrepancies between modules

### 3. Flexibility
- Easy to test different configurations
- Support for environment-specific settings
- Quick policy updates without code changes

### 4. Validation
- Built-in validation prevents invalid configurations
- Warnings for potentially problematic settings

## Usage Examples

### Updating Tax Rate
```python
# In config/business_rules.py
TAX_RATE = 0.095  # Change from 9.4% to 9.5%
```

### Changing Staffing Ratios
```python
# In config/business_rules.py
GUESTS_PER_SERVER = 15  # More attentive service (was 20)
```

### Updating Company Information
```python
# In config/business_rules.py
COMPANY_EMAIL = "contact@newdomain.com"
COMPANY_PHONE = "555-123-4567"
```

## Validation and Testing

### Validate Configuration
```bash
python config/config_manager.py validate
```

### View Current Settings
```bash
python config/config_manager.py summary
```

### Test Configuration
```bash
python test_config.py
```

## Migration Checklist

- ✅ Created centralized configuration system
- ✅ Updated all pricing calculations
- ✅ Updated margin calculations
- ✅ Implemented staffing calculations
- ✅ Updated contract generation
- ✅ Updated validation rules
- ✅ Created configuration management tools
- ✅ Added validation and testing
- ✅ Created documentation

## Next Steps

1. **Test thoroughly** - Run the application with various scenarios
2. **Update documentation** - Ensure all docs reflect new configuration
3. **Train team** - Show team how to update business rules
4. **Monitor** - Watch for any issues with the new system

## Rollback Plan

If issues arise, the old hardcoded values are documented in this guide and can be quickly restored by reverting the configuration imports and restoring the original hardcoded values.

## Support

For questions about the configuration system:
1. Check `config/README.md` for detailed documentation
2. Run `python config/config_manager.py validate` to check for issues
3. Use `python test_config.py` to verify functionality