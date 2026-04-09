from pydantic import BaseModel, validator, ValidationError
from typing import Any, Dict, List, Optional, Pattern, Union
import re
from datetime import datetime, date
from decimal import Decimal
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from functools import wraps
from fastapi import HTTPException, status

class ValidationRules:
    """Centralized validation rules"""
    
    # Password rules
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    PASSWORD_REQUIRE_UPPER = True
    PASSWORD_REQUIRE_LOWER = True
    PASSWORD_REQUIRE_DIGIT = True
    PASSWORD_REQUIRE_SPECIAL = True
    
    # Name rules
    NAME_MIN_LENGTH = 2
    NAME_MAX_LENGTH = 100
    
    # Phone rules
    PHONE_DEFAULT_REGION = "US"
    
    # Address rules
    ADDRESS_MIN_LENGTH = 5
    ADDRESS_MAX_LENGTH = 200
    POSTAL_CODE_PATTERNS = {
        "US": r"^\d{5}(-\d{4})?$",
        "CA": r"^[A-Za-z]\d[A-Za-z] ?\d[A-Za-z]\d$",
        "UK": r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$"
    }
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format"""
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False
    
    @classmethod
    def validate_password(cls, password: str) -> Dict[str, bool]:
        """Validate password strength"""
        checks = {
            "length": cls.PASSWORD_MIN_LENGTH <= len(password) <= cls.PASSWORD_MAX_LENGTH,
            "has_upper": bool(re.search(r'[A-Z]', password)) if cls.PASSWORD_REQUIRE_UPPER else True,
            "has_lower": bool(re.search(r'[a-z]', password)) if cls.PASSWORD_REQUIRE_LOWER else True,
            "has_digit": bool(re.search(r'\d', password)) if cls.PASSWORD_REQUIRE_DIGIT else True,
            "has_special": bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)) if cls.PASSWORD_REQUIRE_SPECIAL else True,
        }
        return checks
    
    @classmethod
    def validate_phone(cls, phone: str, region: str = None) -> bool:
        """Validate phone number"""
        try:
            parsed = phonenumbers.parse(phone, region or cls.PHONE_DEFAULT_REGION)
            return phonenumbers.is_valid_number(parsed)
        except:
            return False
    
    @classmethod
    def validate_postal_code(cls, code: str, country: str = "US") -> bool:
        """Validate postal code for country"""
        pattern = cls.POSTAL_CODE_PATTERNS.get(country.upper())
        if pattern:
            return bool(re.match(pattern, code.strip()))
        return True
    
    @classmethod
    def sanitize_input(cls, text: str, max_length: int = 1000) -> str:
        """Sanitize user input"""
        # Remove dangerous characters
        text = re.sub(r'[<>{}]', '', text)
        # Trim whitespace
        text = text.strip()
        # Limit length
        if len(text) > max_length:
            text = text[:max_length]
        return text

class InputSanitizer:
    """Input sanitization for security"""
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Sanitize string input"""
        if not value:
            return value
        
        # Remove SQL injection patterns
        sql_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b)',
            r'(\b(OR|AND)\s+\d+\s*=\s*\d+\b)',
            r'(\b(UNION|JOIN)\b)'
        ]
        
        for pattern in sql_patterns:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE)
        
        # Remove XSS patterns
        xss_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        for pattern in xss_patterns:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE)
        
        return value.strip()
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = InputSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = InputSanitizer.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    InputSanitizer.sanitize_string(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized

class BusinessValidator:
    """Business logic validators"""
    
    @staticmethod
    def validate_order_total(subtotal: Decimal, shipping: Decimal, total: Decimal) -> bool:
        """Validate order total calculation"""
        expected_total = subtotal + shipping
        return abs(expected_total - total) < Decimal('0.01')
    
    @staticmethod
    def validate_quantity(product_stock: int, requested_qty: int) -> bool:
        """Validate product quantity"""
        return 0 < requested_qty <= product_stock
    
    @staticmethod
    def validate_discount_code(code: str, valid_codes: Dict[str, Dict]) -> Dict:
        """Validate discount code"""
        if code not in valid_codes:
            return {"valid": False, "message": "Invalid discount code"}
        
        discount = valid_codes[code]
        
        # Check expiration
        if discount.get("expires_at") and datetime.now() > discount["expires_at"]:
            return {"valid": False, "message": "Discount code expired"}
        
        # Check usage limit
        if discount.get("max_uses") and discount.get("used_count", 0) >= discount["max_uses"]:
            return {"valid": False, "message": "Discount code usage limit reached"}
        
        return {"valid": True, "discount": discount}

def validate_request(schema_class: BaseModel):
    """Decorator for request validation"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request body
            request_body = kwargs.get('request_body') or kwargs.get('data')
            
            if request_body:
                try:
                    # Validate with schema
                    validated_data = schema_class(**request_body)
                    kwargs['validated_data'] = validated_data
                except ValidationError as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"errors": e.errors()}
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator