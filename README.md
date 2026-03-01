# ClassPulse

<!-- BADGES:START -->
[![audience-engagement](https://img.shields.io/badge/-audience--engagement-blue?style=flat-square)](https://github.com/topics/audience-engagement) [![data-visualization](https://img.shields.io/badge/-data--visualization-blue?style=flat-square)](https://github.com/topics/data-visualization) [![flask](https://img.shields.io/badge/-flask-000000?style=flat-square)](https://github.com/topics/flask) [![html](https://img.shields.io/badge/-html-e34f26?style=flat-square)](https://github.com/topics/html) [![interactive-presentation](https://img.shields.io/badge/-interactive--presentation-blue?style=flat-square)](https://github.com/topics/interactive-presentation) [![python](https://img.shields.io/badge/-python-3776ab?style=flat-square)](https://github.com/topics/python) [![qr-code](https://img.shields.io/badge/-qr--code-blue?style=flat-square)](https://github.com/topics/qr-code) [![real-time](https://img.shields.io/badge/-real--time-blue?style=flat-square)](https://github.com/topics/real-time) [![user-management](https://img.shields.io/badge/-user--management-blue?style=flat-square)](https://github.com/topics/user-management) [![edtech](https://img.shields.io/badge/-edtech-4caf50?style=flat-square)](https://github.com/topics/edtech)
<!-- BADGES:END -->

ClassPulse is a real-time audience engagement web application built with Flask. It allows presenters to create interactive sessions with different question types and receive instant feedback from their audience.

## Features

- **Real-time Interaction**: Engage with your audience in real-time using WebSockets
- **Multiple Question Types**: Create multiple-choice questions, word clouds, and rating scales
- **QR Code Generation**: Easy session joining with auto-generated QR codes
- **Results Visualization**: See responses as they come in with instant updates
- **Data Export**: Export results to CSV for further analysis
- **User Management**: Admin panel for user verification and management
- **Session Archive**: Keep your session history organized

## Question Types

- **Multiple Choice**: Present options and collect structured responses
- **Word Cloud**: Generate word clouds from free-text responses
- **Rating**: Collect numerical ratings on a defined scale

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python app.py
   ```
4. Access the application at http://localhost:5002

## Default Admin Access

- Username: admin
- Password: admin123

⚠️ **Important**: Change the default admin password immediately after first login.

## Requirements

- Python 3.6+
- Flask and extensions (Flask-SQLAlchemy, Flask-SocketIO)
- Additional libraries: qrcode, Pillow

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.