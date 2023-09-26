#!/bin/bash

# execute before export my_passwd=xxxxxx
# Stop webapp service
echo $my_passwd | sudo --stdin systemctl stop webapp-plot-weather.service

# Wait
echo "Waiting 3 second..."
sleep 3
echo "Install new PlotWeatherForRaspi4 application."

# Delete old flask app.
rm -rf ~/PlotWeatherForRaspi4
# Move new flask app in work
mv work/PlotWeatherForRaspi4 ~/PlotWeatherForRaspi4

# Start webapp service
echo $my_passwd | sudo --stdin systemctl start webapp-plot-weather.service
echo "reboot."
echo $my_passwd | sudo --stdin reboot

