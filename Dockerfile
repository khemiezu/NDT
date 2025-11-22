# Use Python 3.12 slim
FROM python:3.12-slim

# Install ffmpeg and dependencies
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy files
COPY . /app

# Install python deps
RUN pip install --no-cache-dir -r requirements.txt

# Expose any port (not required for bot, but Railway likes an exposed port)
ENV PORT 8000
EXPOSE 8000

# Run bot
CMD ["python", "bot.py"]
