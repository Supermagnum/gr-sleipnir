#!/bin/bash
# Valgrind memory leak detection script for gr-sleipnir tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Create valgrind output directory
VALGRIND_OUTPUT_DIR="test_results_comprehensive/valgrind"
mkdir -p "$VALGRIND_OUTPUT_DIR"

# Test a single scenario with valgrind
echo "Running valgrind memory leak detection..."
echo "Output directory: $VALGRIND_OUTPUT_DIR"
echo

# Run a simple test with valgrind
valgrind \
    --leak-check=full \
    --show-leak-kinds=all \
    --track-origins=yes \
    --verbose \
    --log-file="$VALGRIND_OUTPUT_DIR/valgrind_test.log" \
    python3 -c "
import sys
sys.path.insert(0, 'tests')
from flowgraph_builder import build_test_flowgraph
from gnuradio import gr
import time
import gc

print('Creating test flowgraph...')
tb = build_test_flowgraph(
    input_wav='wav/cq_pcm.wav',
    output_wav='/tmp/test_output.wav',
    modulation=4,
    crypto_mode='none',
    channel={'name': 'awgn', 'type': 'awgn'},
    snr_db=10.0,
    test_duration=1.0
)

print('Running flowgraph...')
tb.start()
time.sleep(2.0)
tb.stop()
tb.wait()

print('Cleaning up...')
tb.lock()
tb.unlock()
del tb
gc.collect()

print('Test complete')
"

echo
echo "Valgrind log saved to: $VALGRIND_OUTPUT_DIR/valgrind_test.log"
echo "Review the log for memory leaks and errors."

