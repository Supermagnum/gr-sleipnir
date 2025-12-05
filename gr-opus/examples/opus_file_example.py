#!/usr/bin/env python3
"""
Example: Encode audio file to Opus and decode back
"""

from gnuradio import gr, blocks, filter
from gnuradio import gr_opus
import numpy as np

def main():
    # Create top block
    tb = gr.top_block()
    
    sample_rate = 48000
    
    # Read WAV file
    wav_source = blocks.wavfile_source("input.wav", True)
    
    # Extract audio stream (assuming mono)
    # Note: wavfile_source outputs float samples
    
    # Opus encoder
    encoder = gr_opus.opus_encoder(
        sample_rate=sample_rate,
        channels=1,
        bitrate=64000,
        application='audio'
    )
    
    # Save encoded data to file
    file_sink = blocks.file_sink(gr.sizeof_char, "output.opus")
    file_sink.set_unbuffered(False)
    
    # Connect
    tb.connect(wav_source, encoder)
    tb.connect(encoder, file_sink)
    
    # Run encoding
    print("Encoding audio file...")
    tb.run()
    tb.stop()
    
    # Now decode
    tb2 = gr.top_block()
    
    # Read encoded file
    file_source = blocks.file_source(gr.sizeof_char, "output.opus", False)
    
    # Opus decoder
    decoder = gr_opus.opus_decoder(
        sample_rate=sample_rate,
        channels=1,
        packet_size=0
    )
    
    # Write decoded WAV file
    wav_sink = blocks.wavfile_sink("decoded.wav", 1, sample_rate, 16)
    
    # Connect
    tb2.connect(file_source, decoder)
    tb2.connect(decoder, wav_sink)
    
    # Run decoding
    print("Decoding audio file...")
    tb2.run()
    tb2.stop()
    
    print("Done!")

if __name__ == '__main__':
    main()

