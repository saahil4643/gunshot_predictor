#!/bin/bash

# Deployment helper script for Gunshot Detector

set -e

echo "==================================="
echo "Gunshot Detector Deployment Helper"
echo "==================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Function definitions
build_image() {
    echo "🔨 Building Docker image..."
    docker-compose build
    echo "✅ Image built successfully!"
}

start_app() {
    echo "🚀 Starting application..."
    docker-compose up -d
    echo "✅ Application started!"
    echo ""
    echo "📍 Dashboard available at: http://localhost:6990"
    echo ""
    sleep 2
    docker-compose logs
}

stop_app() {
    echo "🛑 Stopping application..."
    docker-compose down
    echo "✅ Application stopped!"
}

restart_app() {
    echo "🔄 Restarting application..."
    docker-compose restart
    echo "✅ Application restarted!"
}

check_status() {
    echo "📊 Checking application status..."
    docker-compose ps
    echo ""
    echo "Container health:"
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' gunshot-detector 2>/dev/null || echo "Not running")
    echo "Health Status: $HEALTH"
}

setup_env() {
    if [ ! -f .env ]; then
        echo "📝 Creating .env file from template..."
        cp .env.example .env
        echo "✅ .env file created. Please edit it with your email configuration."
        echo "📍 Edit: .env"
    else
        echo "ℹ️  .env file already exists."
    fi
}

view_logs() {
    echo "📋 Showing application logs (Press Ctrl+C to exit)..."
    docker-compose logs -f gunshot-detector
}

clean() {
    echo "🧹 Cleaning up Docker resources..."
    docker-compose down -v
    echo "✅ Cleanup completed!"
}

# Main menu
show_menu() {
    echo ""
    echo "What would you like to do?"
    echo "1) Setup environment (.env file)"
    echo "2) Build Docker image"
    echo "3) Start application"
    echo "4) Stop application"
    echo "5) Restart application"
    echo "6) Check status"
    echo "7) View logs"
    echo "8) Clean up (stop and remove containers)"
    echo "9) Full setup (environment + build + start)"
    echo "0) Exit"
    echo ""
    read -p "Select an option (0-9): " option
}

# Execute option
case "$1" in
    setup)
        setup_env
        ;;
    build)
        build_image
        ;;
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs
        ;;
    clean)
        clean
        ;;
    *)
        # Interactive mode
        while true; do
            show_menu
            case "$option" in
                1) setup_env ;;
                2) build_image ;;
                3) start_app ;;
                4) stop_app ;;
                5) restart_app ;;
                6) check_status ;;
                7) view_logs ;;
                8) clean ;;
                9) setup_env && build_image && start_app ;;
                0) echo "👋 Goodbye!"; exit 0 ;;
                *) echo "❌ Invalid option. Please try again." ;;
            esac
        done
        ;;
esac
