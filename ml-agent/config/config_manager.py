"""
Configuration management utilities for the catering AI agent.
Provides tools to validate, export, and manage business configuration.
"""

import json
import sys
import os
from typing import Dict, Any, List
from decimal import Decimal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.business_rules import BusinessConfig, config


class ConfigManager:
    """Manages business configuration validation and export."""
    
    @staticmethod
    def validate_config() -> Dict[str, Any]:
        """
        Validate the current business configuration.
        
        Returns:
            Dict with validation results and any issues found.
        """
        issues = []
        warnings = []
        
        # Validate tax and fee rates
        if not (0 <= config.TAX_RATE <= 1):
            issues.append(f"TAX_RATE ({config.TAX_RATE}) should be between 0 and 1")
        
        if not (0 <= config.GRATUITY_RATE <= 1):
            issues.append(f"GRATUITY_RATE ({config.GRATUITY_RATE}) should be between 0 and 1")
        
        if not (0 <= config.DEPOSIT_PERCENTAGE <= 1):
            issues.append(f"DEPOSIT_PERCENTAGE ({config.DEPOSIT_PERCENTAGE}) should be between 0 and 1")
        
        # Validate staffing ratios
        if config.GUESTS_PER_SERVER <= 0:
            issues.append(f"GUESTS_PER_SERVER ({config.GUESTS_PER_SERVER}) must be positive")
        
        if config.GUESTS_PER_BARTENDER <= 0:
            issues.append(f"GUESTS_PER_BARTENDER ({config.GUESTS_PER_BARTENDER}) must be positive")
        
        # Validate hourly rates
        if config.SERVER_HOURLY_RATE <= 0:
            issues.append(f"SERVER_HOURLY_RATE ({config.SERVER_HOURLY_RATE}) must be positive")
        
        if config.BARTENDER_HOURLY_RATE <= 0:
            issues.append(f"BARTENDER_HOURLY_RATE ({config.BARTENDER_HOURLY_RATE}) must be positive")
        
        # Validate margin thresholds
        if not (config.MARGIN_CRITICAL_THRESHOLD < config.MARGIN_WARNING_THRESHOLD < config.MARGIN_EXCELLENT_THRESHOLD):
            issues.append("Margin thresholds should be in ascending order: CRITICAL < WARNING < EXCELLENT")
        
        # Validate cost percentages
        if not (0 <= config.FOOD_COST_PERCENTAGE <= 1):
            issues.append(f"FOOD_COST_PERCENTAGE ({config.FOOD_COST_PERCENTAGE}) should be between 0 and 1")
        
        if not (0 <= config.OVERHEAD_PERCENTAGE <= 1):
            issues.append(f"OVERHEAD_PERCENTAGE ({config.OVERHEAD_PERCENTAGE}) should be between 0 and 1")
        
        # Check if total cost percentages seem reasonable
        total_cost_percentage = config.FOOD_COST_PERCENTAGE + config.OVERHEAD_PERCENTAGE
        if total_cost_percentage > 0.8:
            warnings.append(
                f"Combined food and overhead costs ({total_cost_percentage*100:.1f}%) "
                "are very high - may result in low margins"
            )
        
        # Validate rental rates
        for item, rate in config.RENTAL_RATES.items():
            if rate <= 0:
                issues.append(f"RENTAL_RATES['{item}'] ({rate}) must be positive")
        
        # Validate contact info
        if not config.COMPANY_EMAIL or "@" not in config.COMPANY_EMAIL:
            issues.append("COMPANY_EMAIL appears to be invalid")
        
        if not config.COMPANY_PHONE:
            issues.append("COMPANY_PHONE is required")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "summary": f"Found {len(issues)} issues and {len(warnings)} warnings"
        }
    
    @staticmethod
    def export_config(format: str = "json") -> str:
        """
        Export current configuration in the specified format.
        
        Args:
            format: Export format ("json", "yaml", or "env")
            
        Returns:
            Configuration as formatted string
        """
        config_dict = config.to_dict()
        
        if format.lower() == "json":
            return json.dumps(config_dict, indent=2, default=str)
        
        elif format.lower() == "yaml":
            try:
                import yaml
                return yaml.dump(config_dict, default_flow_style=False)
            except ImportError:
                raise ImportError("PyYAML is required for YAML export")
        
        elif format.lower() == "env":
            lines = []
            for key, value in config_dict.items():
                env_key = key.upper()
                if isinstance(value, str):
                    lines.append(f'{env_key}="{value}"')
                else:
                    lines.append(f'{env_key}={value}')
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    @staticmethod
    def get_config_summary() -> Dict[str, Any]:
        """
        Get a summary of current configuration values.
        
        Returns:
            Dictionary with configuration summary
        """
        return {
            "pricing": {
                "tax_rate": f"{config.TAX_RATE*100:.1f}%",
                "gratuity_rate": f"{config.GRATUITY_RATE*100:.0f}%",
                "deposit_percentage": f"{config.DEPOSIT_PERCENTAGE*100:.0f}%",
            },
            "staffing": {
                "guests_per_server": config.GUESTS_PER_SERVER,
                "guests_per_bartender": config.GUESTS_PER_BARTENDER,
                "server_rate": f"${config.SERVER_HOURLY_RATE:.2f}/hr",
                "bartender_rate": f"${config.BARTENDER_HOURLY_RATE:.2f}/hr",
            },
            "costs": {
                "food_cost_percentage": f"{config.FOOD_COST_PERCENTAGE*100:.0f}%",
                "overhead_percentage": f"{config.OVERHEAD_PERCENTAGE*100:.0f}%",
            },
            "margins": {
                "critical_threshold": f"{config.MARGIN_CRITICAL_THRESHOLD:.0f}%",
                "warning_threshold": f"{config.MARGIN_WARNING_THRESHOLD:.0f}%",
                "excellent_threshold": f"{config.MARGIN_EXCELLENT_THRESHOLD:.0f}%",
            },
            "company": {
                "name": config.COMPANY_NAME,
                "email": config.COMPANY_EMAIL,
                "phone": config.COMPANY_PHONE,
            }
        }
    
    @staticmethod
    def compare_configs(other_config: BusinessConfig) -> Dict[str, Any]:
        """
        Compare current config with another configuration.
        
        Args:
            other_config: Another BusinessConfig instance to compare with
            
        Returns:
            Dictionary showing differences
        """
        current = config.to_dict()
        other = other_config.to_dict()
        
        differences = {}
        all_keys = set(current.keys()) | set(other.keys())
        
        for key in all_keys:
            current_val = current.get(key)
            other_val = other.get(key)
            
            if current_val != other_val:
                differences[key] = {
                    "current": current_val,
                    "other": other_val
                }
        
        return {
            "differences": differences,
            "total_differences": len(differences),
            "identical": len(differences) == 0
        }


def validate_configuration():
    """CLI function to validate current configuration."""
    manager = ConfigManager()
    result = manager.validate_config()
    
    print("Configuration Validation Results")
    print("=" * 40)
    print(f"Status: {'✓ VALID' if result['valid'] else '✗ INVALID'}")
    print(f"Summary: {result['summary']}")
    
    if result['issues']:
        print("\nIssues Found:")
        for issue in result['issues']:
            print(f"  ✗ {issue}")
    
    if result['warnings']:
        print("\nWarnings:")
        for warning in result['warnings']:
            print(f"  ⚠ {warning}")
    
    if result['valid'] and not result['warnings']:
        print("\n✓ Configuration is valid and ready for use!")


def print_config_summary():
    """CLI function to print configuration summary."""
    manager = ConfigManager()
    summary = manager.get_config_summary()
    
    print("Business Configuration Summary")
    print("=" * 40)
    
    for section, values in summary.items():
        print(f"\n{section.title()}:")
        for key, value in values.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "validate":
            validate_configuration()
        elif command == "summary":
            print_config_summary()
        elif command == "export":
            format_type = sys.argv[2] if len(sys.argv) > 2 else "json"
            manager = ConfigManager()
            print(manager.export_config(format_type))
        else:
            print("Usage: python config_manager.py [validate|summary|export [json|yaml|env]]")
    else:
        print_config_summary()