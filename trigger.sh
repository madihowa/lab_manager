#!/bin/bash
set -e

# Source secrets
if [ -f "/Users/madihowa/Documents/Programming/hutzler_lab/lab_manager/.secrets" ]; then
    source "/Users/madihowa/Documents/Programming/hutzler_lab/lab_manager/.secrets"
else
    echo "Secrets file not found"
    exit 1
fi

# Activate conda environment
source /Users/madihowa/miniforge3/etc/profile.d/conda.sh
conda activate hl

# Run the Python script and redirect output to a log file
DIR=/Users/madihowa/Documents/Programming/hutzler_lab/lab_manager
# store the python binary path in a variable
PYTHON_BIN=/Users/madihowa/miniforge3/envs/hl/bin/python
# store the path to the python script in a variable
PYTHON_SCRIPT=/Users/madihowa/Documents/Programming/hutzler_lab/lab_manager/main.py
# store the path to the log file in a variable
LOG_FILE=/Users/madihowa/Documents/Programming/hutzler_lab/lab_manager/cron.log

# change directory to the directory of the python script
cd $DIR

# Run the Python script and redirect output to a log file
{
    $PYTHON_BIN $PYTHON_SCRIPT >>$LOG_FILE 2>&1
} || true
EXIT_STATUS=$?

# Marker system implementation
MARKER_PATH="/Users/madihowa/Documents/Programming/hutzler_lab/lab_manager/markers/marker_$(date +%Y-%m-%d).txt"
touch "$MARKER_PATH"
