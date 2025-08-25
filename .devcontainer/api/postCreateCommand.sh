#!/bin/bash
set -e

echo "Updating package lists..."
sudo apt-get update

echo "Installing system dependencies..."
# Install essential libraries for OpenCV and GUI applications
sudo apt-get install -y \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libgl1-mesa-glx \
    libglib2.0-dev \
    libsm6 \
    libice6 \
    libxrandr2 \
    libxss1 \
    libgconf-2-4 \
    libxtst6 \
    libxcomposite1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 || echo "Some packages might already be installed"

# Install MySQL client
echo "Installing MySQL client..."
sudo apt-get install -y default-mysql-client || echo "MySQL client installation failed, continuing..."

echo "Cleaning up package cache..."
sudo apt-get clean
sudo rm -rf /var/lib/apt/lists/*

echo "Installing Python dependencies..."
cd /workspace/src-api
pip install --upgrade pip
pip install -r requirements.txt

echo "postCreateCommand completed successfully!"