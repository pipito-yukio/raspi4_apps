#!/bin/bash

readonly SCRIPT_NAME=${0##*/}

PATH_EXPORT_CSV="$HOME/Downloads/csv"

print_error()
{
   cat << END 1>&2
$SCRIPT_NAME: $1
Try --help option
END
}

next_to_date() {
    retval=$(date -d "$1 1 days" +'%F');
    echo "$retval"
}


get_csv() {
    dev_name="$1";
    where="$2";
cat<<-EOF | sqlite3 "$PATH_WEATHER_DB" -csv
    SELECT
      did,
      datetime(measurement_time, 'unixepoch', 'localtime'), 
      temp_out, temp_in, humid, pressure
    FROM
      t_weather
    WHERE
      did=(SELECT id FROM t_device WHERE name = '${dev_name}') AND (${where})
    ORDER BY measurement_time;
EOF
}

params=$(getopt -n "$SCRIPT_NAME" \
       -o d:f:t:o: \
       -l device-name: -l from-date: -l to-date: -l output-path: -l help \
       -- "$@")

# Check command exit status
if [[ $? -ne 0 ]]; then
  echo 'Try --help option for more information' 1>&2
  exit 1
fi
eval set -- "$params"

# init option value
device_name=
from_date=
to_date=
output_path=$PATH_EXPORT_CSV

# Parse options
# Positional parameter count: $#
while [[ $# -gt 0 ]]
do
  case "$1" in
    -d | --device-name)
      device_name=$2
      shift 2
      ;;
    -f |--from-date)
      from_date=$2
      shift 2
      ;;
    -t | --to-date)
      to_date=$2
      shift 2
      ;;
    -o | --output-path)
      output_path=$2
      shift 2
      ;;
    --help)
      print_help
      exit 0
      ;;
    --)
      shift
      break
      ;;
  esac
done

# Check required option: --device-name
if [ -z "$device_name" ]; then
  print_error "Required --device-name xxxxx"
  exit 1
fi

where=
if [ -n "$from_date" ] && [ -n "$to_date" ]; then
   next_date=$(next_to_date "$to_date");
   where=" measurement_time >= strftime('%s','"$from_date"','-9 hours') AND measurement_time < strftime('%s','"$next_date"','-9 hours')"
fi
if [ -n "$from_date" ] && [ -z "$to_date" ]; then
   where=" measurement_time >= strftime('%s','"$from_date"','-9 hours')"
fi
if [ -z "$from_date" ] && [ -n "$to_date" ]; then
   next_date=$(next_to_date "$to_date");
   where=" measurement_time < strftime('%s','"$next_date"','-9 hours')"
fi
if [ -z "$from_date" ] && [ -z "$to_date" ]; then
   where=" 1=1"
fi
filename="weather.csv"

header='"did","measurement_time","temp_out","temp_in","humid","pressure"'
echo $header > "$output_path/$filename"
get_csv "$device_name" "$where" >> "$output_path/$filename"
if [ $? = 0 ]; then
   echo "Output weather csv to $output_path/$filename"
   row_count=$(cat "${output_path}/${filename}" | wc -l)
   row_count=$(( row_count - 1))
   echo "Record count: ${row_count}" 
fi   

