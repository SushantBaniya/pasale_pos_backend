FROM python:3.13-slim 

WORKDIR /app

RUN pip install --upgrade pip

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev gcc curl gnupg pkg-config libcairo2-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

# Run Daphne server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]