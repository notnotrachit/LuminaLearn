import qrcode
import base64
import io
import json
from django.conf import settings
from django.utils import timezone
import hashlib

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
    try:
        print(f"Received QR data: {json_data}")
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
            print("Missing required fields in QR data")
            return None
        
        # Check expiry if provided
        if result.get('expiry'):
            try:
                expiry = timezone.datetime.fromisoformat(result['expiry'])
                if timezone.now() > expiry:
                    print("QR code has expired")
                    return None
            except ValueError as e:
                print(f"Invalid expiry format: {e}")
                return None
        
        return result
    except Exception as e:
        print(f"Error parsing QR data: {e}")
        return None 