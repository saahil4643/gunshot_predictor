# Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- (Optional) Git for version control

## Quick Start with Docker Compose

### 1. Clone or download the repository
```bash
git clone <repository-url>
cd gunshot_predictor
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:
```bash
cp .env.example .env
```

Edit `.env` with your email configuration:
```env
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@gmail.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

**Note**: For Gmail, you'll need to:
- Enable 2FA on your Google account
- Create an [App Password](https://myaccount.google.com/apppasswords)
- Use the App Password in `SENDER_PASSWORD`

### 3. Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the application
docker-compose up -d

# View logs
docker-compose logs -f gunshot-detector
```

The application will be available at: `http://localhost:6990`

## Docker Build Directly

```bash
# Build image
docker build -t gunshot-detector:latest .

# Run container
docker run -d \
  --name gunshot-detector \
  -p 6990:6990 \
  -v $(pwd)/uploaded_audio:/app/uploaded_audio \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/testing_chunks:/app/testing_chunks \
  -v $(pwd)/model:/app/model \
  -e SENDER_EMAIL="your-email@gmail.com" \
  -e SENDER_PASSWORD="your-app-password" \
  -e RECIPIENT_EMAIL="recipient@gmail.com" \
  gunshot-detector:latest
```

## Stopping the Application

```bash
# Stop with Docker Compose
docker-compose down

# Or stop individual container
docker stop gunshot-detector
docker rm gunshot-detector
```

## Production Deployment

### AWS ECS
1. Push image to ECR:
   ```bash
   docker tag gunshot-detector:latest <aws_account>.dkr.ecr.<region>.amazonaws.com/gunshot-detector:latest
   docker push <aws_account>.dkr.ecr.<region>.amazonaws.com/gunshot-detector:latest
   ```
2. Create ECS task definition with environment variables
3. Create ECS service

### Google Cloud Run
```bash
gcloud builds submit --tag gcr.io/<project>/gunshot-detector
gcloud run deploy gunshot-detector \
  --image gcr.io/<project>/gunshot-detector \
  --platform managed \
  --region us-central1 \
  --set-env-vars SENDER_EMAIL=<email>,SENDER_PASSWORD=<password>
```

### Azure Container Instances
```bash
az container create \
  --resource-group <group> \
  --name gunshot-detector \
  --image gunshot-detector:latest \
  --ports 6990 \
  --environment-variables SENDER_EMAIL=<email> SENDER_PASSWORD=<password>
```

## Health Checks

The application includes a health check endpoint. Check container health:

```bash
docker-compose ps
# or
docker inspect --format='{{.State.Health.Status}}' gunshot-detector
```

## Volumes

The Docker setup persists the following directories:
- `uploaded_audio/` - User uploaded audio files
- `config/` - Configuration files (receiver email settings)
- `testing_chunks/` - Live detection test chunks
- `model/` - ML models (mount as read-only for production)

## Performance Considerations

- **Memory**: Allocate at least 2GB RAM
- **GPU**: Add `--gpus all` flag to Docker run for GPU acceleration with TensorFlow
- **Disk**: Ensure sufficient disk space for audio uploads and model files

## Troubleshooting

### Container won't start
```bash
docker-compose logs gunshot-detector
```

### Permission denied errors
```bash
chmod -R 755 uploaded_audio config testing_chunks
```

### Model files not found
Ensure `model/` directory contains:
- `final_audio_model_v4.h5`
- `final_gunshot_model.h5`

### Email not sending
- Verify SMTP credentials in `.env`
- Check Gmail App Password (not regular password)
- Ensure sender email is configured in environment

## Security Best Practices

1. **Never commit `.env` file to version control**
2. **Use strong passwords/app passwords**
3. **Restrict port access with firewall rules**
4. **Mount model files as read-only in production**
5. **Regularly backup `config/receiver_email.txt`**
6. **Use secrets management services** (AWS Secrets Manager, Azure Key Vault, etc.)

## Port Configuration

Default port is `6990`. To change:
1. Update `docker-compose.yml` port mapping
2. Or pass `-p <new_port>:6990` to docker run

## Next Steps

- Configure receiver email through the web UI hamburger menu
- Upload test audio files
- Enable live detection
- Monitor emails for alerts
