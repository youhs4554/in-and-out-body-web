#!/bin/bash

# Find the process ID (PID) running on port 8000
PID=$(lsof -t -i:8000)

# If a process is found, kill it
if [ -n "$PID" ]; then
    echo "Killing process $PID running on port 8000"
    kill -9 $PID
fi

# Restart the Django server
echo "Starting Django server..."
python manage.py runserver &