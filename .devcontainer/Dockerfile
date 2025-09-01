# DevContainer für Running Dinner mit Docker-in-Docker
FROM mcr.microsoft.com/devcontainers/python:3.11-bullseye

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI and Docker Compose
RUN curl -fsSL https://get.docker.com | sh \
    && curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker-compose

# Set up workspace
WORKDIR /workspaces/RunningDinner

# Install Python dependencies during build
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Add vscode user to docker group
RUN usermod -aG docker vscode

# Development tools
RUN pip install ipython django-extensions

USER vscode
