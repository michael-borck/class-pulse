import string
import secrets
import qrcode
import csv
import io
from io import BytesIO
import base64
from datetime import datetime

def generate_session_code(length=6):
    """
    Generate a random alphanumeric session code of specified length.
    
    Args:
        length (int): Length of the session code to generate. Default is 6.
        
    Returns:
        str: Random alphanumeric session code
    """
    # Using characters that are less likely to be confused
    alphabet = ''.join(c for c in string.ascii_uppercase + string.digits if c not in 'O0I1')
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_qr_code(data, size=10, border=4):
    """
    Generate a QR code image for the given data
    and return it as a base64-encoded PNG.
    
    Args:
        data (str): Data to encode in the QR code, typically a URL
        size (int): QR code box size. Default is 10.
        border (int): QR code border width. Default is 4.
        
    Returns:
        str: Base64 encoded image data
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=size,
        border=border
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')

def get_join_url(session_code, base_url=None):
    """
    Generate the audience join URL for a session code.
    
    Args:
        session_code (str): Session code to create URL for
        base_url (str, optional): Base URL of the application. 
                                 If None, uses relative URL. Default is None.
                                  
    Returns:
        str: URL for joining the session
    """
    if base_url:
        # Remove trailing slash if present
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        return f"{base_url}/join/{session_code}"
    else:
        # Return a relative URL if no base_url is provided
        return f"/join/{session_code}"

def get_qr_code_img_tag(url, alt_text="Scan to join"):
    """
    Generate a complete HTML img tag with base64 encoded QR code.
    
    Args:
        url (str): URL to encode in the QR code
        alt_text (str): Alternative text for the img tag
        
    Returns:
        str: HTML img tag with encoded QR code
    """
    qr_data = generate_qr_code(url)
    return f'<img src="data:image/png;base64,{qr_data}" alt="{alt_text}" class="qr-code">'

def export_results_to_csv(session_code, questions, responses):
    """
    Generate a CSV file from session results.
    
    Args:
        session_code (str): The session code
        questions (list): List of question objects
        responses (list): List of response objects
        
    Returns:
        io.StringIO: CSV data as a string buffer
    """
    # Create a StringIO object to hold CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['Session Code', 'Question', 'Question Type', 'Response', 'Timestamp'])
    
    # Write data rows
    for response in responses:
        question = next((q for q in questions if q['id'] == response['question_id']), None)
        if question:
            writer.writerow([
                session_code,
                question['text'],
                question['type'],
                response['answer'],
                response.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            ])
    
    # Reset the pointer to the beginning of the StringIO object
    output.seek(0)
    return output

def get_timestamp():
    """
    Get the current timestamp formatted for display.
    
    Returns:
        str: Current timestamp as a formatted string
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
