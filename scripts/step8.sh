#!/bin/zsh
# Long runs of steps 7-10 in pieces: stop any time, start again later; finished seeds are kept, not rerun.
#
#   scripts/step8.sh start    # start (or resume) the job queue in the background, machine kept awake
#   scripts/step8.sh stop     # stop now; seeds that were running are rerun on start
#   scripts/step8.sh pause    # stop by itself once the runs going now have finished, so no run is lost
#   scripts/step8.sh status   # queue state and log tail
#
# Queue, 5 sumo processes at a time: step 10 sensitivity runs (sensitivity.py). Steps 7-9 were run through this
# script on 4-9 Nov 2569 (run_rain.py, run_flood_traffic.py, run_scenarios.py run, run_playback.py).
cd "${0:A:h}/.."
PY=.venv/bin/python
QUEUE="$PY scripts/sensitivity.py run"
JOB='[s]ensitivity.py run|[r]un_playback.py|[r]un_flood_traffic.py|[r]un_scenarios.py run|[r]un_rain.py --reroute'
SUMO="$PWD/.venv/lib/python3.12/site-packages/sumo/bin/sumo"

case $1 in
  start)
    if pgrep -f "$JOB" >/dev/null; then echo 'already running'; exit 1; fi
    rm -f output/step8_paused.txt
    nohup caffeinate -is zsh -c "$QUEUE" >> output/step8_queue.log 2>&1 &
    echo $! > output/.queue.pid
    echo "started $(date '+%d %b %H:%M'), log: output/step8_queue.log" ;;
  stop)  # the whole process tree of the queue, collected before killing: pool workers outlive their parent
    # and start new sumo runs, and sumo under TraCI ignores SIGTERM while its client is gone
    tree() { echo $1; for c in $(pgrep -P $1); do tree $c; done }
    pids=($( [ -f output/.queue.pid ] && tree $(cat output/.queue.pid) ) $(pgrep -f "$JOB") $(pgrep -f "$SUMO"))
    pids=(${(u)pids})
    [ ${#pids} -gt 0 ] && kill $pids 2>/dev/null
    for i in {1..15}; do ps -p ${(j:,:)pids} >/dev/null 2>&1 || break; sleep 1; done
    for p in $pids; do  # only processes of this queue, in case a pid was reused
      ps -p $p -o command= 2>/dev/null | grep -qE 'Phuket-Traffic-Flood-Sim|multiprocessing|caffeinate -is zsh' && kill -9 $p
    done
    rm -f output/.queue.pid
    echo "stopped $(date '+%d %b %H:%M')" ;;
  pause)  # waits until as many runs have finished as were running when pause was called
    n=$(pgrep -f "$SUMO" | wc -l | tr -d ' ')
    # each finished run prints a '... done' line to the log (sumo creates its output files when it starts)
    k=$(( $(grep -c ' done$' output/step8_queue.log 2>/dev/null || echo 0) + n ))
    nohup zsh -c "
      while pgrep -f '$JOB' >/dev/null && [ \$(grep -c ' done\$' output/step8_queue.log) -lt $k ]; do
        sleep 20
      done
      ${0:A} stop
      echo \"paused \$(date '+%d %b %H:%M') after the running seeds finished\" > output/step8_paused.txt
    " > /dev/null 2>&1 &
    echo "will stop after the $n running seeds finish; check output/step8_paused.txt" ;;
  status)
    pgrep -f "$JOB" >/dev/null && echo 'running' || echo 'not running'
    tail -3 output/step8_queue.log 2>/dev/null
    $PY scripts/sensitivity.py summary | tail -12 ;;
  *) echo "usage: $0 start|stop|pause|status"; exit 1 ;;
esac
