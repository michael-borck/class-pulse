# ClassPulse Deployment Guide

This guide explains how to deploy ClassPulse as a systemd service on Ubuntu/Debian systems.

## Prerequisites

- Python 3.8 or higher
- Git
- System with systemd (Ubuntu, Debian, etc.)
- User with sudo privileges

## Installation Steps

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

## Accessing the Application

Once the service is running, you can access ClassPulse at:
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

To update ClassPulse:

```bash
# Stop the service
sudo systemctl stop classpulse

# Pull the latest changes
cd /home/michael/projects/class-pulse
git pull

# Restart the service
sudo systemctl start classpulse
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