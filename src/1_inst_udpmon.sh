#!/bin/bash

# execute before export my_passwd=xxxxxx

# Add [ip address] [hostname].local in /etc/hosts
ip_addr=$(ifconfig eth0 | grep "inet " | awk '{ print $2 }')
host_in_hosts=$(cat /etc/hosts | grep 127.0.1.1 | awk '{ print $2 }')
host_in_hosts="${host_in_hosts}.local"
add_dot_host="${ip_addr}		${host_in_hosts}"
echo $my_passwd | { sudo --stdin chown pi.pi /etc/hosts
  echo $add_dot_host>>/etc/hosts
  sudo chown root.root /etc/hosts
}

echo $my_passwd | { sudo --stdin apt update && sudo apt -y upgrade
   sudo apt -y install python3-venv sqlite3 docker-compose
   sudo apt -y autoremove
}

# Create Virtual Python environment.
if [ ! -d "$HOME/py_venv" ]; then
   mkdir py_venv
fi

cd py_venv
python3 -m venv raspi4_apps
. raspi4_apps/bin/activate
pip install -U pip
# requirements.txt in psycopg2-binary flask waitress pandas matplotlib libraries.
pip install -r ~/work/requirements.txt
exit1=$?
echo "Install requirements libraries into raspi4_apps >> status=$exit1"
deactivate
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

cd ~/

# docker execute to pi
echo $my_passwd | sudo --stdin gpasswd -a pi docker

# Enable pigpio app system services
echo $my_passwd | { sudo --stdin cp ~/work/etc/default/postgres-12-docker /etc/default
  sudo cp ~/work/etc/systemd/system/postgres-12-docker.service /etc/systemd/system
  sudo cp ~/work/etc/systemd/system/cleanup-postgres-12-docker.service /etc/systemd/system
  sudo cp ~/work/etc/systemd/system/udp-weather-mon.service /etc/systemd/system
  sudo systemctl enable postgres-12-docker.service
  sudo systemctl enable cleanup-postgres-12-docker.service
  sudo systemctl enable udp-weather-mon.service
}

echo "Done, logout this terminqal."

