import pyotp
import qrcode
from io import BytesIO
import base64
from typing import Tuple, Optional
from app.models.user import User

class MFAService:
    """Multi-factor authentication service"""
    
    @staticmethod
    def generate_secret() -> str:
        """Generate TOTP secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def get_totp_uri(secret: str, email: str) -> str:
        """Get TOTP URI for QR code"""
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name="Roots"
        )
    
    @staticmethod
    def generate_qr_code(secret: str, email: str) -> str:
        """Generate QR code as base64 string"""
        uri = MFAService.get_totp_uri(secret, email)
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        
        return base64.b64encode(buffered.getvalue()).decode()
    
    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        """Verify TOTP code"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    
    @staticmethod
    def get_backup_codes() -> list:
        """Generate backup codes for account recovery"""
        import secrets
        return [secrets.token_hex(4) for _ in range(10)]