#!/bin/bash

export APPDIR=$HOME/oci-nightly-stop

cd $APPDIR


###########################################################
# Main
###########################################################
echo "Start running at `date`..."
echo
start_time=$(date +%s)

FILTER_TZ="NONE"
FILTER_MODE="exclude"

# Check the number of arguments
if [ "$#" -eq 1 ]; then
    FILTER_TZ=$1
    FILTER_MODE="include"
elif [ "$#" -ge 2 ]; then
    FILTER_TZ=$1
    FILTER_MODE=$2
fi

echo "Filtered Timezone: $FILTER_TZ"
echo "Filter Mode: $FILTER_MODE"
echo

python3 -u $APPDIR/nightly-stop.py --filter-tz $FILTER_TZ --filter-mode $FILTER_MODE 

echo
echo "Completed at `date`.."
end_time=$(date +%s)

elapsed_seconds=$((end_time - start_time))

hours=$((elapsed_seconds / 3600))
minutes=$(( (elapsed_seconds % 3600) / 60 ))
seconds=$((elapsed_seconds % 60))

echo "Elapsed time: $hours hours, $minutes minutes, $seconds seconds"

# Delete old logs
find "$APPDIR" -type f -name "run_nightly-stop.sh_run.txt_*" -mtime +10 -exec rm -f {} \;