#!/bin/bash
# Create timestamped archive of test results, log files and JSON files

DATE=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="test-results-archive_${DATE}.tar.gz"
ARCHIVE_DIR="archives"

echo "Creating test results archive..."
echo "Timestamp: $DATE"
echo "Archive name: $ARCHIVE_NAME"
echo

# Create archives directory if it doesn't exist
mkdir -p "$ARCHIVE_DIR"

# Create archive excluding WAV files and output-wav directory
tar --exclude='*.wav' \
    --exclude='output-wav' \
    --exclude='*.tar.gz' \
    --exclude='archives' \
    -czf "$ARCHIVE_DIR/$ARCHIVE_NAME" \
    test-results-json/ \
    test-results-files/ \
    test_results_comprehensive/ \
    *.log \
    nohup.out 2>/dev/null || true

if [ -f "$ARCHIVE_DIR/$ARCHIVE_NAME" ]; then
    echo "✓ Archive created successfully"
    echo "  Location: $ARCHIVE_DIR/$ARCHIVE_NAME"
    echo "  Size: $(du -h "$ARCHIVE_DIR/$ARCHIVE_NAME" | cut -f1)"
    echo "  Files: $(tar -tzf "$ARCHIVE_DIR/$ARCHIVE_NAME" | wc -l)"
    echo
    echo "Archive contents:"
    tar -tzf "$ARCHIVE_DIR/$ARCHIVE_NAME" | head -20
    echo "..."
else
    echo "✗ Archive creation failed"
    exit 1
fi
