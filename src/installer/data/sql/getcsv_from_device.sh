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

query() {
   sqlite3 -cmd 'PRAGMA foreign_key=ON' "$PATH_WEATHER_DB" "$@"
}

get_csv() {
cat<<-EOF | query -csv
    SELECT id, name FROM t_device ORDER BY id;
EOF
}

params=$(getopt -n "$SCRIPT_NAME" \
       -o o: \
       -l help -l output-path: \
       -- "$@")

# Check command exit status
if [[ $? -ne 0 ]]; then
  echo 'Try --help option for more information' 1>&2
  exit 1
fi
eval set -- "$params"

# init option value
output_path=$PATH_EXPORT_CSV

# Parse options
# Positional parameter count: $#
while [[ $# -gt 0 ]]
do
  case "$1" in
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

filename="device.csv"

header='"id","name"'
echo $header > "$output_path/$filename"
get_csv >> "$output_path/$filename"
if [ $? = 0 ]; then
   echo "Output device csv to $output_path/$filename"
   row_count=$(cat "${output_path}/${filename}" | wc -l)
   row_count=$(( row_count - 1))
   echo "Record count: ${row_count}" 
fi   

