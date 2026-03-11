# Business Configuration System

This directory contains the centralized business configuration for the catering AI agent. All hardcoded business rules, rates, and policies have been moved here for easy maintenance and updates.

## Files

- `business_rules.py` - Main configuration class with all business rules
- `config_manager.py` - Utilities for validating and managing configuration
- `__init__.py` - Package initialization

## Key Features

### Centralized Configuration
All business logic is now centralized in `BusinessConfig` class:
- Tax rates and fees
- Staffing ratios and labor rates
- Margin thresholds and cost percentages
- Pricing rules and package selection
- Cancellation policies
- Company information

### Easy Updates
Update business rules by modifying values in `business_rules.py`:

```python
# Change tax rate
TAX_RATE = 0.094  # 9.4%

# Update staffing ratios
GUESTS_PER_SERVER = 20  # 1 server per 20 guests

# Modify margin thresholds
MARGIN_CRITICAL_THRESHOLD = 20.0  # Below 20% is critical
```

### Configuration Validation
Validate your configuration changes:

```bash
python config/config_manager.py validate
```

### Export Configuration
Export current configuration for backup or documentation:

```bash
# Export as JSON
python config/config_manager.py export json

# Export as environment variables
python config/config_manager.py export env
```

### View Configuration Summary
Get a quick overview of current settings:

```bash
python config/config_manager.py summary
```

## Usage in Code

Import and use the configuration throughout the application:

```python
from config.business_rules import config

# Use tax rate
tax = subtotal * config.TAX_RATE

# Calculate service surcharge
surcharge = config.calculate_service_surcharge(guest_count, service_type)

# Get margin status
status = config.get_margin_status(margin_percentage)
```

## Configuration Categories

### Pricing & Financial Rules
- Tax rates (9.4%)
- Gratuity rates (20%)
- Deposit percentage (50%)
- Payment processing fees

### Staffing Rules
- Staff-to-guest ratios
- Hourly rates for different roles
- Minimum staffing requirements
- Event duration assumptions

### Margin & Cost Rules
- Food cost percentage (32%)
- Overhead percentage (18%)
- Margin thresholds for warnings

### Policies
- Cancellation and refund policies
- Guest count variance rules
- Additional labor charges

### Company Information
- Company name and legal name
- Contact information
- Contract formatting rules

## Benefits

1. **Maintainability** - All business rules in one place
2. **Consistency** - Same values used throughout the application
3. **Flexibility** - Easy to update rates and policies
4. **Validation** - Built-in validation prevents invalid configurations
5. **Documentation** - Clear documentation of all business rules
6. **Testing** - Easy to test with different configuration values

## Migration from Hardcoded Values

The following hardcoded values have been moved to configuration:

- Tax rate (9.4%) → `config.TAX_RATE`
- Gratuity rate (20%) → `config.GRATUITY_RATE`
- Staffing ratios → `config.GUESTS_PER_SERVER`, `config.GUESTS_PER_BARTENDER`
- Labor rates → `config.SERVER_HOURLY_RATE`, `config.BARTENDER_HOURLY_RATE`
- Margin thresholds → `config.MARGIN_*_THRESHOLD`
- Rental rates → `config.RENTAL_RATES`
- Company info → `config.COMPANY_*`

## Future Enhancements

Potential future improvements:
- Environment variable overrides
- Database-backed configuration
- Web-based configuration management
- A/B testing different configurations
- Historical configuration tracking