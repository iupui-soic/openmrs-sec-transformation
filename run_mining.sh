#!/usr/bin/env bash
# Run a list of pipeline scripts with timestamped logging. Built to run under tmux
# (survives disconnects). Usage: run_mining.sh <logname> <script1.py> [script2.py ...]
set -u
cd "$(dirname "$0")" || exit 1
mkdir -p logs
logname="${1:?need a log name}"; shift
log="logs/${logname}.log"
{
  echo "######## RUN ${logname} pid=$$ $(date +'%F %T') ########"
  for s in "$@"; do
    echo "=== START ${s} $(date +'%F %T') ==="
    python3 "scripts/${s}"
    echo "=== EXIT $? ${s} $(date +'%F %T') ==="
  done
  echo "######## ALL DONE $(date +'%F %T') ########"
} 2>&1 | tee -a "$log"
