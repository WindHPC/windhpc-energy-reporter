t_start=$(date +%s)

sleep 190

t_end=$(date +%s)

echo "Start: $t_start End: $t_end"
python3 ./energy-reporter.py --start $t_start --end $t_end n012001 n012201 n012401 n012601
