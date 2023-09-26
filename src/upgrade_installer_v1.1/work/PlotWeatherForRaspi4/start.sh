#!/bin/bash

# ./start.sh                    -> development
# ./start.sh prod | production  ->production

env_mode="development"
if [ $# -eq 0 ]; then
    :
else
   if [[ "$1" = "prod" || "$1" = "production" ]]; then 
        env_mode="production"
   fi
fi

host_name="$(/bin/cat /etc/hostname)"
IP_HOST_ORG="${host_name}.local"   # ADD host suffix ".local"
export IP_HOST="${IP_HOST_ORG,,}"  # to lowercase
export FLASK_ENV=$env_mode
echo "$IP_HOST with $FLASK_ENV"

EXEC_PATH=
if [ -n "$PATH_PLOT_WEATHER" ]; then
   EXEC_PATH=$PATH_PLOT_WEATHER
else
   EXEC_PATH="$HOME/PlotWeatherForRaspi4"
fi

. $HOME/py_venv/raspi4_apps/bin/activate

python $EXEC_PATH/run.py

deactivate
