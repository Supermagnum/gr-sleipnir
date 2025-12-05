#!/usr/bin/env python3
"""
Example GNU Radio flowgraph demonstrating Opus encoding and decoding
"""

from gnuradio import gr, audio, blocks
from gnuradio import gr_opus

def main():
    # Create top block
    tb = gr.top_block()
    
    # Sample rate
    sample_rate = 48000
    
    # Create blocks
    # Audio source (microphone input)
    src = audio.source(sample_rate, "hw:0,0")
    
    # Opus encoder
    encoder = gr_opus.opus_encoder(
        sample_rate=sample_rate,
        channels=1,
        bitrate=64000,
        application='audio'
    )
    
    # Opus decoder
    decoder = gr_opus.opus_decoder(
        sample_rate=sample_rate,
        channels=1,
        packet_size=0  # Auto-detect packet size
    )
    
    # Audio sink (speaker output)
    sink = audio.sink(sample_rate, "hw:0,0")
    
    # Connect blocks
    tb.connect(src, encoder)
    tb.connect(encoder, decoder)
    tb.connect(decoder, sink)
    
    # Run
    tb.start()
    input("Press Enter to stop...")
    tb.stop()
    tb.wait()

if __name__ == '__main__':
    main()

