#!/bin/bash

# Load environment variables from the .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Find the process ID (PID) running on port 8000
PID=$(lsof -t -i:8000)

# If a process is found, kill it
if [ -n "$PID" ]; then
    echo "Killing process $PID running on port 8000"
    kill -9 $PID
fi

# Check the environment and run collectstatic only if ENVIRONMENT is "prod"
if [ "$ENVIRONMENT" == "prod" ]; then
    echo "Running collectstatic..."
    echo "yes" | python manage.py collectstatic
else
    echo "Skipping collectstatic because ENVIRONMENT is not 'prod'."
fi

# Restart the Django server
echo "Starting Django server..."
nohup python manage.py runserver 0.0.0.0:8000 > /tmp/nohup.log 2>&1 &