#!/bin/bash


cd "$(dirname "$0")"
TIMESTAMP=$(date --iso-8601=seconds)
FILE=$(basename $PWD)
echo $(pwd)
# Check if binary exists
if [ ! -f "bin/$FILE" ]; then
    echo "Binary not found! Please run ./build.sh first"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p log

# Check if already running
if pgrep -f "bin/$FILE" > /dev/null; then
    echo "$FILE is already running!"
    ./status.sh
    exit 1
fi

echo "Starting $FILE server..."
nohup bin/$FILE >> log/out.txt 2>> log/err.txt &

# Wait a moment for the process to start
sleep 2

echo "$FILE started at $TIMESTAMP" >> log/run.log
echo "Server should be running on http://localhost:8080"
echo "Logs: log/out.txt and log/err.txt"

./status.sh

