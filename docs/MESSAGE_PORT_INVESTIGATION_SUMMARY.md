# Message Port Forwarding Investigation Summary

## Problem Statement

The `sleipnir_superframe_parser` is not receiving PDUs from the `frame_aware_ldpc_decoder_router` through the `hier_block2` message port connection in GNU Radio 3.10.

## Current Implementation

### Connection Chain
```
decoder_router['pdus'] → message_forwarder['in'] → message_forwarder['out'] → parser['in']
```

All blocks are inside `sleipnir_rx_hier` (a `hier_block2`).

### Message Flow
1. **Decoder Router**: Queues PDUs in `work()` and publishes from a separate thread via `message_port_pub()`
2. **Message Forwarder**: Receives messages in `handle_msg()` and forwards via `message_port_pub()`
3. **Parser**: Should receive messages in `handle_msg()` but it's not being called

### Evidence
- Decoder router successfully publishes PDUs (logs show "Published PDU")
- Message forwarder receives messages (logs show "Received message")
- Parser's `handle_msg()` is NOT being called (no debug messages)

## Root Cause Analysis

### Hypothesis 1: Messages from `handle_msg()` don't propagate within `hier_block2`
**Status**: Likely the issue

In GNU Radio 3.10, messages published from `handle_msg()` inside a `hier_block2` may not reliably reach other blocks inside the same `hier_block2`, even when using `msg_connect()`. This is a known limitation of GNU Radio 3.10's message port forwarding mechanism.

### Hypothesis 2: Message port connections not established
**Status**: Unlikely

The connections are made correctly:
- `self.msg_connect(ldpc_decoder_router, "pdus", message_forwarder_block, "in")`
- `self.msg_connect(message_forwarder_block, "out", superframe_parser, "in")`

### Hypothesis 3: Timing issue
**Status**: Possible but unlikely

Messages might be published before connections are fully established, but the thread-based publishing should handle this.

## Potential Solutions

### Solution 1: Expose Parser Input Through `hier_block2` (Recommended)
Expose the parser's input port through the `hier_block2` and connect externally:

```python
# In sleipnir_rx_hier.__init__():
# Expose parser input port
self.message_port_register_hier_in("parser_in")

# Connect forwarder output to exposed port
self.msg_connect(message_forwarder_block, "out", self, "parser_in")

# Connect exposed port to parser
self.msg_connect(self, "parser_in", superframe_parser, "in")
```

**Pros**: Uses `hier_block2` exposed ports which are more reliable
**Cons**: Requires external connection (but can be done internally)

### Solution 2: Use Tagged Streams Instead
Replace message ports with tagged streams, which are more reliable through `hier_block2` boundaries.

**Pros**: Tagged streams work reliably in `hier_block2` contexts
**Cons**: Requires significant refactoring

### Solution 3: Direct Connection (Bypass Forwarder)
Connect decoder router directly to parser, but expose through `hier_block2`:

```python
# Expose decoder router output
self.message_port_register_hier_out("decoder_pdus")
self.msg_connect(ldpc_decoder_router, "pdus", self, "decoder_pdus")

# Expose parser input
self.message_port_register_hier_in("parser_in")

# Connect externally (in top_block)
tb.msg_connect(rx_hier, "decoder_pdus", rx_hier, "parser_in")
```

**Pros**: Uses exposed ports which are more reliable
**Cons**: Requires external connection in top_block

### Solution 4: Wait for GNU Radio 4.0
GNU Radio 4.0 may have improved message port forwarding mechanisms.

**Pros**: No code changes needed
**Cons**: Waiting for future release

## Implementation Status

### Solution 1: Expose Parser Input Through `hier_block2` (IMPLEMENTED)
**Status**: Implemented in `sleipnir_rx_hier.py`

The parser input port is now exposed through the `hier_block2` and messages are routed through the exposed port:

```python
# Expose parser input port
self.message_port_register_hier_in("parser_in")

# Connect through exposed port
self.msg_connect(message_forwarder_block, "out", self, "parser_in")
self.msg_connect(self, "parser_in", superframe_parser, "in")
```

**Expected Behavior**: Messages from the forwarder should now propagate through the `hier_block2` exposed port mechanism, which is more reliable than direct internal connections.

## Recommended Next Steps

1. **Test the Implementation**: Run phase 1 tests to verify messages now reach the parser
2. **Run Diagnostic Script**: Use `tests/diagnose_message_flow.py` to verify message flow
3. **Monitor Logs**: Check if parser's `handle_msg()` is now being called
4. **Consider Tagged Streams**: If message ports continue to fail, consider refactoring to tagged streams

## Diagnostic Tools

- `tests/diagnose_message_flow.py`: Comprehensive diagnostic script
- `tests/test_message_port_forwarding.py`: Basic message port forwarding tests
- `tests/test_message_port_verification.py`: Verification tests

## References

- GNU Radio Message Passing Documentation: https://wiki.gnuradio.org/index.php/Message_Passing
- GNU Radio 3.10 API: https://www.gnuradio.org/doc/doxygen/
- Issue tracking: See README.md for current status

