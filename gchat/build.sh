#!/bin/bash
FILE=$(basename $PWD)
TIMESTAMP=$(date --iso-8601=seconds)

echo "Building $FILE..."

# Create necessary directories
mkdir -p bin old log

# Move old binary if exists
if [ -f "./bin/$FILE" ]; then
    echo "Backing up old binary..."
    #mv -f --backup=numbered "./bin/$FILE" "./old/$FILE"
    rm -f ./bin/$FILE
fi

# Initialize go module if needed
if [ ! -f "go.mod" ]; then
    echo "Initializing Go module..."
    go mod init gchat
fi

# Download dependencies
echo "Downloading dependencies..."
go mod tidy

# Build the application
echo "Compiling Go application..."
cd app
go build -o "../bin/$FILE"
BUILD_RESULT=$?
cd ..

if [ $BUILD_RESULT -eq 0 ]; then
    echo "Build successful!"
    echo "* $FILE build completed at $TIMESTAMP" >> log/build.log
    echo "Binary created: bin/$FILE"
else
    echo "Build failed!"
    echo "* $FILE build FAILED at $TIMESTAMP" >> log/build.log
    exit 1
fi

