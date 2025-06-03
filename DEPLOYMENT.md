# ClassPulse Deployment Guide

This guide explains multiple ways to deploy ClassPulse:
1. As a systemd service (production)
2. Using Docker and Docker Compose
3. Using the Makefile for quick setup
4. Manual development setup

## Prerequisites

- Python 3.8 or higher
- Git
- For systemd: Ubuntu/Debian system with sudo privileges
- For Docker: Docker and Docker Compose installed

## Method 1: Systemd Service (Recommended for Production)

### 1. Clone the Repository

```bash
git clone https://github.com/michael-borck/class-pulse.git
cd class-pulse
```

### 2. Run the Setup Script

The `start.sh` script will:
- Create a Python virtual environment
- Install all required dependencies
- Start the application with gunicorn

```bash
./start.sh
```

Press `Ctrl+C` to stop the application after verifying it works.

### 3. Install as a Systemd Service

Copy the service file to the systemd directory:

```bash
sudo cp classpulse.service /etc/systemd/system/
```

### 4. Configure the Service

If needed, edit the service file to match your environment:

```bash
sudo nano /etc/systemd/system/classpulse.service
```

Key settings to verify:
- `User=` and `Group=` - Should match your username
- `WorkingDirectory=` - Path to your ClassPulse installation
- `ExecStart=` - Path to the start.sh script

### 5. Enable and Start the Service

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable classpulse.service

# Start the service
sudo systemctl start classpulse.service
```

### 6. Verify the Service is Running

```bash
# Check the service status
sudo systemctl status classpulse.service

# View real-time logs
sudo journalctl -u classpulse -f
```

## Service Management

### Common Commands

- **Start the service:** `sudo systemctl start classpulse`
- **Stop the service:** `sudo systemctl stop classpulse`
- **Restart the service:** `sudo systemctl restart classpulse`
- **Check status:** `sudo systemctl status classpulse`
- **Disable auto-start:** `sudo systemctl disable classpulse`

### Viewing Logs

```bash
# View all logs
sudo journalctl -u classpulse

# View last 100 lines
sudo journalctl -u classpulse -n 100

# Follow logs in real-time
sudo journalctl -u classpulse -f

# View logs from today
sudo journalctl -u classpulse --since today
```

## Method 2: Docker Deployment

Docker provides an isolated environment and is great for containerized deployments.

### 1. Clone and Navigate to Repository

```bash
git clone https://github.com/michael-borck/class-pulse.git
cd class-pulse
```

### 2. Build and Run with Docker Compose

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### 3. Alternative: Build and Run with Docker

```bash
# Build the Docker image
docker build -t classpulse:latest .

# Run the container
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/instance:/app/instance \
  -e SECRET_KEY=your-secret-key-here \
  --name classpulse \
  classpulse:latest

# View logs
docker logs -f classpulse

# Stop the container
docker stop classpulse
docker rm classpulse
```

## Method 3: Using Makefile

The Makefile provides convenient commands for both development and production setup.

### 1. Clone the Repository

```bash
git clone https://github.com/michael-borck/class-pulse.git
cd class-pulse
```

### 2. Setup Commands

```bash
# Development setup (includes dev tools)
make setup

# Production setup
make setup-prod

# Run development server
make run

# Run production server with gunicorn
make prod

# Initialize database
make db-init

# Run linting and formatting
make lint
make format

# Clean up cache files
make clean
```

### 3. Docker Commands via Makefile

```bash
# Build Docker image
make docker-build

# Start with Docker Compose
make docker-up

# Stop Docker Compose
make docker-down
```

## Method 4: Manual Development Setup

For development or testing purposes, you can run the application manually.

### 1. Clone the Repository

```bash
git clone https://github.com/michael-borck/class-pulse.git
cd class-pulse
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Initialize Database

```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### 5. Run the Application

```bash
# Development server
python app.py

# Production server with gunicorn
gunicorn --workers=4 --bind=0.0.0.0:5000 --worker-class=gthread --threads=2 wsgi:application
```

## Accessing the Application

Regardless of the deployment method, you can access ClassPulse at:
- Local: http://localhost:5000
- Network: http://YOUR_SERVER_IP:5000

## Troubleshooting

### Service Won't Start

1. Check the logs for errors:
   ```bash
   sudo journalctl -u classpulse -n 50
   ```

2. Verify the start.sh script is executable:
   ```bash
   chmod +x /home/michael/projects/class-pulse/start.sh
   ```

3. Test running the script manually:
   ```bash
   cd /home/michael/projects/class-pulse
   ./start.sh
   ```

### Permission Issues

Ensure the user specified in the service file has:
- Read access to all application files
- Write access to the instance directory
- Execute permission on start.sh

### Port Already in Use

If port 5000 is already in use, either:
1. Stop the conflicting service
2. Change the port in start.sh (modify the `--bind` parameter)

## Updating the Application

### For Systemd Service

```bash
# Stop the service
sudo systemctl stop classpulse

# Pull the latest changes
cd /home/michael/projects/class-pulse
git pull

# Restart the service
sudo systemctl start classpulse
```

### For Docker

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

### For Manual Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Pull latest changes
git pull

# Update dependencies
pip install -r requirements.txt

# Restart your application
```

## Security Considerations

1. **Firewall**: Configure your firewall to allow traffic on port 5000
2. **HTTPS**: Consider using a reverse proxy (nginx/Apache) for SSL/TLS
3. **Environment Variables**: Store sensitive configuration in environment files
4. **Database**: For production, consider using PostgreSQL instead of SQLite

## Reverse Proxy Setup (Optional)

For production deployments, it's recommended to use nginx as a reverse proxy:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /socket.io {
        proxy_pass http://127.0.0.1:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Support

For issues or questions:
- Check the [GitHub repository](https://github.com/michael-borck/class-pulse)
- Review application logs using journalctl
- Ensure all dependencies are properly installed