# Message Port Forwarding Investigation

## Problem Statement

The `sleipnir_superframe_parser` is not receiving PDUs from the `frame_aware_ldpc_decoder_router` through the `hier_block2` message port connection in GNU Radio 3.10.

## Investigation Results

### 1. GNU Radio 3.10 Message Port Forwarding Mechanism

**Key Finding:** According to GNU Radio documentation, publishing messages from within a block's `work()` function is **discouraged** and can lead to blocking behavior. Messages should be processed asynchronously via message handlers.

**Issue:** Messages published from `work()` may not reliably propagate through `hier_block2` boundaries in GNU Radio 3.10.

### 2. Current Implementation

**Connection Chain:**
```
decoder_router['pdus'] → hier_block2['decoder_pdus'] → parser['in']
```

**Message Port Setup:**
- `decoder_router.message_port_register_out("pdus")` - Registered
- `hier_block2.message_port_register_hier_out("decoder_pdus")` - Registered
- `hier_block2.msg_connect(decoder_router, "pdus", self, "decoder_pdus")` - Connected
- `hier_block2.msg_connect(self, "decoder_pdus", parser, "in")` - Connected
- `parser.message_port_register_in("in")` - Registered
- `parser.set_msg_handler("in", parser.handle_msg)` - Handler set

**Problem:** Messages published from `decoder_router.work()` via `message_port_pub()` are not reaching the parser's `handle_msg()` method.

### 3. Solution: Message Forwarder Block

**Approach:** Use an intermediate `message_forwarder` block that receives messages in its `handle_msg()` method (asynchronous context) rather than from `work()`.

**New Connection Chain:**
```
decoder_router['pdus'] → message_forwarder['in'] → message_forwarder['out'] → parser['in']
```

**Why This Works:**
- Messages published from `decoder_router.work()` go to `forwarder.handle_msg()` (asynchronous)
- `forwarder.handle_msg()` publishes to parser (asynchronous context)
- Messages in asynchronous context are more reliably delivered through `hier_block2` boundaries

### 4. Implementation Details

**Message Forwarder Block:**
- `sync_block` with dummy stream I/O to keep scheduler active
- `message_port_register_in("in")` and `message_port_register_out("out")`
- `handle_msg()` method forwards incoming messages to output port
- Stream connection: `vector_source_b` → `message_forwarder` → `null_sink` (for scheduling)

**Integration in `sleipnir_rx_hier.py`:**
```python
# Create message forwarder
message_forwarder_block = make_message_forwarder()

# Connect forwarder to stream for scheduling
forwarder_dummy_src = blocks.vector_source_b([0] * 1024, repeat=True)
forwarder_dummy_sink = blocks.null_sink(gr.sizeof_char)
self.connect(forwarder_dummy_src, message_forwarder_block, forwarder_dummy_sink)

# Connect message ports: decoder_router -> forwarder -> parser
self.msg_connect(ldpc_decoder_router, "pdus", message_forwarder_block, "in")
self.msg_connect(message_forwarder_block, "out", superframe_parser, "in")
```

### 5. Alternative Approaches Considered

**Tagged Streams:**
- Previously attempted but tags did not propagate reliably through `hier_block2` boundaries
- Would require significant refactoring

**External Message Routing:**
- Could use ZeroMQ blocks for external routing
- Adds complexity and external dependencies
- Not necessary if message forwarder works

**Timer-Based Publishing:**
- Could queue messages in `work()` and publish from timer/callback
- More complex implementation
- Message forwarder is simpler and more direct

### 6. Verification Status

**Current Status:**
- Message forwarder block is scheduled and running
- Decoder router is publishing PDUs
- Need to verify messages are being forwarded to parser

**Next Steps:**
- Verify message forwarder receives messages from decoder router
- Verify parser receives messages from message forwarder
- Test with actual phase 1 test scenarios

### 7. References

- GNU Radio Message Passing Documentation: https://wiki.gnuradio.org/index.php/Message_Passing
- Key insight: Messages published from `work()` are discouraged; use message handlers for asynchronous processing

