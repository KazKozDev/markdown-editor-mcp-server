# Use a slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY . .

# Install the package in editable mode or just install dependencies
RUN pip install --no-cache-dir .

# Expose no ports (MCP uses stdio)

# Default command to run the server
ENTRYPOINT ["python", "-m", "markdown_editor.server"]
