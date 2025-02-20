# Use a minimal Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY bot.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the bot
CMD ["python", "bot.py"]