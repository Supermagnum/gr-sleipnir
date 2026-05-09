# gr-satellites Message Block Analysis

## Overview

Analysis of how gr-satellites (Daniel Estévez) implements message-only blocks that process PDUs, focusing on patterns that ensure proper scheduling and message delivery.

## Key Findings

### 1. Message-Only Blocks Use `gr.basic_block` with Empty Stream Signatures

**Example: `telemetry_parser` and `file_receiver`**

```python
class telemetry_parser(gr.basic_block):
    def __init__(self, definition, file=sys.stdout, options=None):
        gr.basic_block.__init__(
            self,
            'telemetry_parser',
            in_sig=[],      # Empty list - no stream input
            out_sig=[])     # Empty list - no stream output
        
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
    
    def handle_msg(self, msg_pmt):
        # Process message
        pass
```

**Key Points:**
- Uses `gr.basic_block` (not `gr.sync_block`)
- `in_sig=[]` and `out_sig=[]` (empty lists, NOT `None`)
- Only implements `handle_msg()` - **NO `general_work()` implementation**
- No dummy stream connections needed
- Blocks work correctly without explicit `general_work()`

### 2. Blocks with Stream Input Use `gr.sync_block` with Message Output

**Example: `hdlc_deframer`**

```python
class hdlc_deframer(gr.sync_block):
    def __init__(self, check_fcs, max_length, crc_check_func=None):
        gr.sync_block.__init__(
            self,
            name='hdlc_deframer',
            in_sig=[numpy.uint8],  # Real stream input
            out_sig=None)           # No stream output
        
        self.message_port_register_out(pmt.intern('out'))
    
    def work(self, input_items, output_items):
        # Process stream input
        # Publish messages via message_port_pub()
        self.message_port_pub(pmt.intern('out'), pdu)
        return len(input_items[0])
```

**Key Points:**
- Uses `gr.sync_block` when there's real stream input
- `out_sig=None` (not empty list) when there's no stream output
- Publishes messages from `work()` function
- Stream input keeps block scheduled

### 3. Hierarchical Blocks Wrap Message Blocks

**Example: `hexdump_sink`**

```python
class hexdump_sink(gr.hier_block2):
    def __init__(self, options=None):
        gr.hier_block2.__init__(
            self,
            'hexdump_sink',
            gr.io_signature(0, 0, 0),  # No stream I/O
            gr.io_signature(0, 0, 0))
        
        self.message_port_register_hier_in('in')
        
        self.message_debug = blocks.message_debug()
        self.msg_connect((self, 'in'), (self.message_debug, 'print'))
```

**Key Points:**
- Uses `hier_block2` to wrap GNU Radio built-in blocks
- Message ports forwarded through hierarchical boundaries
- Works correctly in GNU Radio 3.11

## Comparison with Our Implementation

### Current Parser Implementation

```python
class sleipnir_superframe_parser(gr.sync_block):  # Bad practice: Using sync_block
    def __init__(self, ...):
        gr.sync_block.__init__(
            self,
            name="sleipnir_superframe_parser",
            in_sig=[np.byte],   # Bad practice: Dummy input
            out_sig=[np.byte])  # Bad practice: Dummy output
        
        # ... message port setup ...
    
    def work(self, input_items, output_items):
        # Dummy work function
        return n
    
    def handle_msg(self, msg):
        # Process message
        pass
```

### Recommended Fix Based on gr-satellites Pattern

```python
class sleipnir_superframe_parser(gr.basic_block):  # Use basic_block
    def __init__(self, ...):
        gr.basic_block.__init__(
            self,
            name="sleipnir_superframe_parser",
            in_sig=[],   # Empty list - no stream input
            out_sig=[])  # Empty list - no stream output
        
        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
        
        # ... output ports ...
    
    # NO general_work() needed - GNU Radio handles it automatically
    # NO work() function - this is basic_block, not sync_block
    
    def handle_msg(self, msg):
        # Process message
        pass
```

## Critical Differences

1. **Block Type**: Use `gr.basic_block` (not `gr.sync_block`) for message-only blocks
2. **Stream Signatures**: Use empty lists `[]` (not `None` or dummy types) for `in_sig` and `out_sig`
3. **No `general_work()`**: Don't implement `general_work()` - GNU Radio handles it automatically for `basic_block`
4. **No Dummy Streams**: Don't connect dummy stream sources/sinks - message-only blocks don't need them
5. **Message Handler**: Only implement `handle_msg()` - this is called automatically when messages arrive

## Why This Works

According to GNU Radio's architecture:
- `gr.basic_block` is designed for message-only blocks
- When `in_sig=[]` and `out_sig=[]`, GNU Radio knows it's a message-only block
- The scheduler automatically calls message handlers when messages arrive
- No need for `general_work()` unless you need custom scheduling behavior
- Message port connections trigger the scheduler to deliver messages

## Next Steps

1. Change `sleipnir_superframe_parser` from `gr.sync_block` to `gr.basic_block`
2. Change `in_sig=[np.byte]` to `in_sig=[]` (empty list)
3. Change `out_sig=[np.byte]` to `out_sig=[]` (empty list)
4. Remove `work()` function (not needed for `basic_block`)
5. Remove `general_work()` if it exists (not needed - GNU Radio provides default)
6. Remove dummy stream connections in `flowgraph_builder.py`
7. Test to verify messages are delivered and `handle_msg()` is called

## References

- gr-satellites repository: https://github.com/daniestevez/gr-satellites
- Key files examined:
  - `python/components/datasinks/telemetry_parser.py` - Pure message-only block
  - `python/components/datasinks/file_receiver.py` - Pure message-only block
  - `python/hdlc_deframer.py` - Stream input + message output
  - `python/components/datasinks/hexdump_sink.py` - Hierarchical wrapper

