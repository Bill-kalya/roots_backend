from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
import os
from typing import Optional, Dict, Any
import json
from app.core.config import settings

class DataEncryption:
    """Enterprise data encryption for sensitive data at rest"""
    
    def __init__(self):
        self._encryption_keys: Dict[str, bytes] = {}
        self._initialize_keys()
    
    def _initialize_keys(self):
        """Initialize encryption keys from environment or KMS"""
        # Primary key for general data
        primary_key = os.environ.get("ENCRYPTION_KEY")
        if not primary_key:
            # Generate key for development (in production, use KMS)
            primary_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
            print(f"WARNING: Generated new encryption key. Store this safely: {primary_key}")
        
        self._encryption_keys["primary"] = primary_key.encode()
        
        # PII key for personal data
        pii_key = os.environ.get("PII_ENCRYPTION_KEY")
        if pii_key:
            self._encryption_keys["pii"] = pii_key.encode()
        else:
            self._encryption_keys["pii"] = self._encryption_keys["primary"]
    
    def _get_cipher(self, key_name: str = "primary") -> Fernet:
        """Get Fernet cipher for encryption"""
        key = self._encryption_keys.get(key_name)
        if not key:
            raise ValueError(f"Encryption key {key_name} not found")
        return Fernet(key)
    
    def encrypt(self, data: str, key_name: str = "primary") -> str:
        """Encrypt string data"""
        cipher = self._get_cipher(key_name)
        encrypted = cipher.encrypt(data.encode())
        return encrypted.decode()
    
    def decrypt(self, encrypted_data: str, key_name: str = "primary") -> str:
        """Decrypt string data"""
        cipher = self._get_cipher(key_name)
        decrypted = cipher.decrypt(encrypted_data.encode())
        return decrypted.decode()
    
    def encrypt_json(self, data: Dict[str, Any], key_name: str = "primary") -> str:
        """Encrypt JSON data"""
        json_str = json.dumps(data)
        return self.encrypt(json_str, key_name)
    
    def decrypt_json(self, encrypted_data: str, key_name: str = "primary") -> Dict[str, Any]:
        """Decrypt JSON data"""
        json_str = self.decrypt(encrypted_data, key_name)
        return json.loads(json_str)
    
    def encrypt_sensitive_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in a dictionary"""
        sensitive_fields = ['email', 'phone', 'ssn', 'credit_card', 'password', 'address']
        
        encrypted_data = data.copy()
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[f"{field}_encrypted"] = self.encrypt(
                    str(encrypted_data[field]),
                    "pii"
                )
                del encrypted_data[field]
        
        return encrypted_data
    
    def decrypt_sensitive_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in a dictionary"""
        decrypted_data = data.copy()
        
        for key in list(decrypted_data.keys()):
            if key.endswith('_encrypted'):
                original_field = key.replace('_encrypted', '')
                decrypted_data[original_field] = self.decrypt(
                    decrypted_data[key],
                    "pii"
                )
                del decrypted_data[key]
        
        return decrypted_data

# Global encryption instance
encryption = DataEncryption()

class FieldEncryption:
    """Descriptor for automatic field encryption in models"""
    
    def __init__(self, key_name: str = "pii"):
        self.key_name = key_name
        self.internal_name = None
    
    def __set_name__(self, owner, name):
        self.internal_name = f"_{name}"
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        encrypted_value = getattr(obj, self.internal_name, None)
        if encrypted_value:
            return encryption.decrypt(encrypted_value, self.key_name)
        return None
    
    def __set__(self, obj, value):
        if value:
            encrypted = encryption.encrypt(str(value), self.key_name)
            setattr(obj, self.internal_name, encrypted)
        else:
            setattr(obj, self.internal_name, None)