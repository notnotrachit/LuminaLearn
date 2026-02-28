import qrcode
import base64
import io
import json
import logging
from django.conf import settings
from django.utils import timezone
import hashlib

logger = logging.getLogger(__name__)

def generate_qr_code(lecture_id, nonce, expiry_timestamp=None):
    """
    Generate a QR code image for attendance
    
    Args:
        lecture_id: ID of the lecture
        nonce: Random nonce for verification
        expiry_timestamp: When this QR code expires
        
    Returns:
        Base64 encoded PNG image of the QR code
    """
    # Create data payload - simplify the data structure for better scanning
    data = {
        'l': lecture_id,
        'n': nonce,
        'e': expiry_timestamp.isoformat() if expiry_timestamp else None
    }
    
    # Convert to JSON - use a compact format
    json_data = json.dumps(data, separators=(',', ':'))
    
    # Create QR code with highest error correction and bigger size
    qr = qrcode.QRCode(
        version=2,  # Use version 2 for compact data
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Highest error correction
        box_size=15,  # Larger boxes for better scanning
        border=4,
    )
    qr.add_data(json_data)
    qr.make(fit=True)
    
    # Create image with better contrast
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

def verify_qr_data(json_data, max_age_seconds=300):
    """
    Verify QR code data is valid

    Args:
        json_data: JSON data from QR code
        max_age_seconds: Maximum age of QR code in seconds

    Returns:
        dict: Parsed data if valid, None otherwise
    """
    import logging as log_module
    func_logger = log_module.getLogger(__name__)

    try:
        func_logger.debug("Processing QR code data")
        data = json.loads(json_data)

        # Check if new compact format or old format
        if 'l' in data and 'n' in data:
            # Using new compact format
            lecture_id = data['l']
            nonce = data['n']
            expiry = data.get('e')

            # Convert to original format for compatibility
            result = {
                'lecture_id': lecture_id,
                'nonce': nonce,
                'expiry': expiry
            }
        elif 'lecture_id' in data and 'nonce' in data:
            # Using original format
            result = data
        else:
            func_logger.warning("Missing required fields in QR data")
            return None

        # Check expiry if provided - handle both timezone-aware and naive datetimes
        if result.get('expiry'):
            try:
                from datetime import datetime, timezone as dt_timezone

                expiry_str = result['expiry']

                # Parse aware datetime; fallback to treating as UTC if no offset present
                try:
                    expiry = datetime.fromisoformat(expiry_str)
                except ValueError:
                    # Python < 3.11: strip trailing Z if present
                    expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))

                # Make naive datetimes UTC-aware before comparison
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=dt_timezone.utc)

                if timezone.now() > expiry:
                    func_logger.info("QR code has expired")
                    return None
            except (ValueError, TypeError) as e:
                func_logger.warning(f"Invalid expiry format in QR data: {e}")
                return None

        return result
    except Exception as e:
        func_logger.error(f"Error parsing QR data: {e}")
        return None 