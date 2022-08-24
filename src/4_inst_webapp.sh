#!/bin/bash

# execute before export my_passwd=xxxxxx

# https://moji.or.jp/ipafont/installation
# For Linux installation exmaple.
# .fonts/IPAfont
fc-cache -fv
fc-list | grep -i ipa

# Enable webapp service
echo $my_passwd | { sudo --stdin cp ~/work/etc/default/webapp-plot-weather /etc/default
  sudo cp ~/work/etc/systemd/system/webapp-plot-weather.service /etc/systemd/system
  sudo systemctl enable webapp-plot-weather.service
}

echo "rebooting."
echo $my_passwd |sudo --stdin reboot

