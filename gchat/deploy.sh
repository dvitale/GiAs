#!/bin/bash

echo "=== Web2Rasa Deployment Script ==="

# Build the application
echo "Step 1: Building application..."
if ./build.sh; then
    echo "✓ Build completed successfully"
else
    echo "✗ Build failed!"
    exit 1
fi

# Stop existing instance if running
echo "Step 2: Stopping existing instance..."
./stop.sh

# Start the application
echo "Step 3: Starting application..."
if ./run.sh; then
    echo "✓ Deployment completed successfully"
    echo ""
    echo "Application is now running at: http://localhost:8080"
    echo "Check status with: ./status.sh"
    echo "View logs with: tail -f log/out.txt"
else
    echo "✗ Failed to start application!"
    exit 1
fi