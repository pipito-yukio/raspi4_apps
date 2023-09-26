#!/bin/bash

. ${HOME}/py_venv/raspi4_apps/bin/activate

python ${HOME}/bin/pigpio/UdpMonitorFromWeatherSensor.py

deactivate
