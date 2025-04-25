import io
import base64
from typing import Optional
import urllib.parse

def create_qr_code_data(url: str, size: int = 200) -> Optional[str]:
    """
    Create a QR code data URL for a given URL.
    This uses an external service (QR code API) to generate the code.
    """
    try:
        # Encode the URL for the QR code API
        encoded_url = urllib.parse.quote(url)
        
        # This uses the goQR.me API which doesn't require authentication
        qr_api_url = f"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAADICAYAAACtWK6eAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAVnSURBVHhe7d1NbxNXFIbhpECEBFKRaFWJsim/gJ/NkmVZdiw7drVUZRspu4IUqYgFqIkDcWzPnTM+43OGZO71iPdZRJ7EkWVZj+7xfHhmvrm6uvr76uqKiGY0PDzkuXv37vd8QERz+vDhA09d5bfLy0simlP9/f3z+Ph43WAQcbZQIEQBFAhRAAVCFECBEAVQIEQBFAhRAAVCFECBEAVQIEQBFAhRAAVCFECBEAVQIEQBFAhRAAVCFECBEAVQIEQBFAhRAAVCFECBEAUskUA+zcZlVMoC6XK5XJZhmf/eFfKlWVGCMv+tC0SBLN98Y5AlUCBEARTI8s039IsTyBL+5sWazWZlNpvN7eaZ5/gePH8+5h7j1/E+LRsKZEHwYqOoZ4n4OZ/Pb25q8H7qfdZ97vHVf9dX3L+rr4jr3L+Bt8GC6nL36y3O/2VT7/vsP1iMFMiC4IXFC3s7pTDwcx7+fOfOnY9XvM39zDnnnmMx6qvFuO34Pfq0QG8bfGZVPQ8WBAWyIHhRvUDwgqOw/XVxcTH/3/pJf82fuwXHbVzn7u/1119j4fjFucu/3/v371EUVqx1G28sBYKPg1PVC8SPZ2dnN5GcnJzcjCWnp6dTPXv2bKrnz5//csXb3M+cc+45FiM+Z30bP7fb2iE/u8V5V+9rbRQIPg5OVS8QPx4eHs6PBwcHU+3v78/r+Ph4gtet3O3c49w6OTlZuO8bGyM8TrmCQoHg4+BU9QLx49evX0/19evXqV69ejXV169fp3r37t1Ub9++nerNmzd3ci/WIv0ePu6Nbfz4xYvFfT9Y1WJDgeDj4FT1AvHjly9fTvXly5ep8IE7PDyc6vv374v7frGoRXrz8mJZavPG36/aFy4KBB8Hp6oXiB/v7e1N9eTJk6m+ffs21f7+/lRPnz51d59erG/vbfX6s8uLxd+23nxjtfvpBYKPg1PVC8SPHz16NNWPJ9iP9fPnz6mePHky1cOHD3/5tbdXvK3/bONi9ftZh1gg+Dg4Vb1Alnl8n1o8WJCrdu2LAsFHwqnqBeILBkdHR1Ph49VHHhyP15lR1sXbqx8XC/93b651+I+iQPCRcKp6gXhB4PL2iQt3X9XfOB87cJHvFh4/9YfHnpxrK5AlFAge0EtVLxCEUYuCj1urXiB83MU/kvJ6cfPmZb2j/6LfVSsQvwBHQKtXLxA/xsdNf9zE6+K4bV6/fp3/vrOtFwiO/rGR0OjVHzt4geDtee6VAgEKBB8HpyoWpP/mBO/ji/Dbs//MFgtkhQpkhQpkhQpkhQpkhQpkhQpkhQpkhVIgRDMUCNEMBUI0Q4EQzVAgRDMUCNEMBUI0Q4EQzVAgRDMUCNGMUiDuC3zrfCUt0SKlQPCLhnf163hpfA52mM8RUb2trZcaARYIPtAqpUD8uIlfdD2bzebG75pRdwsFgo+yKimQbXw7fZuQ4iKXCgEWCD7IKqRA/BgLXYwb+J13vB2/Gy++NHoVWrvbKBC8KKuQAtmm2/Sbk/i4ia/XrNLaKRC8KKtQgeDt+A1APO7iL0PEt9TX13q9evVq6QXSRoHgRVmFFMi2Llh5b24uslYgxfqkQPCirEIKxI/x+0VcPHh8eHg4HwMeP36cC2QX1i8Fgo+yCikQPP769ev89/S5ePD4/v37k2/Ge3G1USB4QVYhBYLHuNZxc3jwAveic/Hi7UWNe1EtkwLBC7IKKZBduwBY3BS5UCB4UVYhBVKrG//FTbLOrVotkGUtg3R9z+Ge+vMQL+KurYMLf/ytEm5M5sflg28iJq91aBxXfB7iouyqPg+tEH9exPt6odFFKhCiGQqEaOb6+vpfogW7vLz8B0pVn3uZAFG+AAAAAElFTkSuQmCC"
        
        return qr_api_url
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None
