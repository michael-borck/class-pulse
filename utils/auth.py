import hashlib
import secrets
import time
from models.schema import users, User

def hash_password(password, salt=None):
    """
    Hash a password for storage.
    If salt is not provided, a new one will be generated.
    """
    if not salt:
        salt = secrets.token_hex(16)
    
    # Create salted hash
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    
    # Return the salt and hash together
    return f"{salt}${hashed}"

def verify_password(stored_password, provided_password):
    """
    Verify a stored password against the provided password
    """
    # Split the stored password into salt and hash
    salt, stored_hash = stored_password.split('$', 1)
    
    # Hash the provided password with the same salt
    calculated_hash = hashlib.pbkdf2_hmac(
        'sha256',
        provided_password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    
    # Check if the calculated hash matches the stored hash
    return stored_hash == calculated_hash

def register_user(username, password, email, display_name=None):
    """
    Register a new user
    """
    # Check if username already exists
    admin_users = users(where="username = ?", where_args=[username])
    if admin_users:
        return False, "Username already exists"
    
    # Hash the password
    password_hash = hash_password(password)
    
    # Use display name or username if not provided
    if not display_name:
        display_name = username
    
    # Create user
    try:
        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            display_name=display_name
        )
        users.insert(user)
        return True, "User registered successfully"
    except Exception as e:
        return False, str(e)

def authenticate_user(username, password):
    """
    Authenticate a user by username and password
    """
    # Find user by username
    user_records = users(where="username = ?", where_args=[username])
    
    if not user_records:
        return None
    
    user = user_records[0]
    
    # Verify password
    if verify_password(user.password_hash, password):
        return user
    
    return None

# Create a default admin user on import if none exists
admin_users = users(where="username = ?", where_args=["admin"])
if not admin_users:
    register_user('admin', 'admin123', 'admin@classpulse.local', 'Admin')
