#!/usr/bin/env bash
# Run the QuantumC pipeline on each C file in a corpus (random order, serial).
# Usage:
#   bash tools/check_pipeline_corpus.sh [CORPUS_DIR]
#
# Env:
#   ENV=cotenv   # conda env name (optional)
#   BITS=16      # pipeline bits
#   MAX_ITER=30  # pipeline max unroll
#   NO_SHUF=0    # set 1 to disable randomization

set -u

ENV_NAME=${ENV:-cotenv}
CORPUS_DIR=${1:-corpus}
BITS=${BITS:-16}
MAX_ITER=${MAX_ITER:-30}
NO_SHUF=${NO_SHUF:-0}

name_base=$(basename "$CORPUS_DIR")
RESULTS_DIR="tools/results"
LOG_DIR="$RESULTS_DIR/pipeline_logs_${name_base}"
SUMMARY_CSV="$RESULTS_DIR/${name_base}_pipeline_summary.csv"
OK_LIST="$RESULTS_DIR/${name_base}_pipeline_ok.txt"
FAIL_LIST="$RESULTS_DIR/${name_base}_pipeline_fail.txt"

mkdir -p "$RESULTS_DIR" "$LOG_DIR"

echo "file,status,exit_code,qasm_path,qasm_exists,elapsed_s" > "$SUMMARY_CSV"
: > "$OK_LIST"
: > "$FAIL_LIST"

# Choose runner (prefer conda if available)
if command -v conda >/dev/null 2>&1; then
  RUN_CMD="conda run -n $ENV_NAME python"
else
  echo "[warn] 'conda' not found, using system 'python'"
  RUN_CMD="python"
fi

shopt -s nullglob
mapfile -t files < <(printf "%s\n" "$CORPUS_DIR"/*.c)
if [ ${#files[@]} -eq 0 ]; then
  echo "No .c files in '$CORPUS_DIR'"; exit 1
fi

# Randomize order unless NO_SHUF=1
if [ "$NO_SHUF" -ne 1 ]; then
  if command -v shuf >/dev/null 2>&1; then
    mapfile -t files < <(printf "%s\n" "${files[@]}" | shuf)
  else
    # Fisher–Yates with $RANDOM
    for ((i=${#files[@]}-1; i>0; i--)); do
      j=$((RANDOM % (i+1)))
      tmp=${files[i]}; files[i]=${files[j]}; files[j]=$tmp
    done
  fi
fi

count_total=0
count_ok=0
count_fail=0

for f in "${files[@]}"; do
  base=$(basename "$f" .c)
  sout="$LOG_DIR/${base}.stdout"
  serr="$LOG_DIR/${base}.stderr"
  qasm="output/${base}.qasm"

  start_ns=$(date +%s%N 2>/dev/null || echo 0)

  # run serially
  bash -lc "$RUN_CMD pipeline.py \"$f\" --bits \"$BITS\" --max-iter \"$MAX_ITER\" >\"$sout\" 2>\"$serr\""
  rc=$?

  end_ns=$(date +%s%N 2>/dev/null || echo 0)
  if [[ "$start_ns" != 0 && "$end_ns" != 0 ]]; then
    elapsed=$(awk -v s="$start_ns" -v e="$end_ns" 'BEGIN{printf "%.3f", (e-s)/1e9}')
  else
    elapsed=""
  fi

  if [[ $rc -eq 0 && -f "$qasm" ]]; then
    echo "$f,ok,$rc,$qasm,1,$elapsed" >> "$SUMMARY_CSV"
    echo "$f" >> "$OK_LIST"
    printf "[OK]    %s\n" "$f"
    ((count_ok++))
  else
    exists=0; [[ -f "$qasm" ]] && exists=1
    echo "$f,error,$rc,$qasm,$exists,$elapsed" >> "$SUMMARY_CSV"
    echo "$f" >> "$FAIL_LIST"
    printf "[ERROR] %s (rc=%d)\n  stderr -> %s\n" "$f" "$rc" "$serr"
    ((count_fail++))
  fi
  ((count_total++))
done

echo
echo "Summary: total=$count_total ok=$count_ok error=$count_fail"
echo "Details:"
echo "  CSV:   $SUMMARY_CSV"
echo "  OK:    $OK_LIST"
echo "  FAIL:  $FAIL_LIST"
echo "  Logs:  $LOG_DIR/{<file>.stdout,<file>.stderr}"
