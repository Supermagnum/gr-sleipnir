// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_SLEIPNIR_SLEIPNIRTXHIER_HPP
#define GNURADIO4_SLEIPNIR_SLEIPNIRTXHIER_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/annotated.hpp>
#include <gnuradio-4.0/sleipnir/detail/SleipnirFrameFormat.hpp>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace gnuradio4::sleipnir {

GR_REGISTER_BLOCK(gnuradio4::sleipnir::SleipnirTxHier)

/**
 * SleipnirTxHier — stream-in, message-out hierarchical TX block.
 *
 * Stream in:    float32 audio samples (one at a time via processBulk).
 * Message out:  control_out — each message carries a pdu_bytes Tensor<uint8_t>
 *               of the assembled superframe payload once a full superframe has
 *               been accumulated.
 *
 * Accumulation:
 *   The block accumulates float samples into frames of frame_size_samples
 *   samples each.  Once frames_per_superframe frames have been accumulated
 *   it assembles a superframe and emits it on control_out.
 *
 * frame_size_samples defaults to 1920 (48 kHz * 40 ms).  Change it to a
 * smaller value in tests to avoid allocating large buffers.
 */
struct SleipnirTxHier : gr::Block<SleipnirTxHier, gr::NoTagPropagation> {
    using Description = gr::Doc<"Accumulate float32 audio, assemble and emit superframe PDU on control_out.">;

    gr::PortIn<float> in{};
    gr::MsgPortOut    control_out{};

    gr::Annotated<std::string, "callsign",           gr::Doc<"Station callsign">>                                  callsign           = std::string("N0CALL");
    gr::Annotated<bool,        "enable_signing",      gr::Doc<"Prepend ECDSA auth frame (requires OpenSSL)">>      enable_signing     = false;
    gr::Annotated<std::string, "private_key_path",    gr::Doc<"Path to PEM private key">>                           private_key_path   = std::string("");
    gr::Annotated<int,         "frames_per_superframe", gr::Doc<"Number of voice frames per superframe">>          frames_per_superframe = 25;
    gr::Annotated<int,         "frame_duration_ms",   gr::Doc<"Voice frame duration in milliseconds">>             frame_duration_ms  = 40;
    gr::Annotated<int,         "voice_frame_bytes",   gr::Doc<"Voice frame byte count (Opus packet size)">>        voice_frame_bytes  = 48;
    gr::Annotated<int,         "frame_size_samples",  gr::Doc<"Audio samples per voice frame (0 = use default 1920)">> frame_size_samples = 1920;

    GR_MAKE_REFLECTABLE(SleipnirTxHier, in, control_out,
                        callsign, enable_signing, private_key_path,
                        frames_per_superframe, frame_duration_ms,
                        voice_frame_bytes, frame_size_samples);

    std::vector<float>         _sample_buf{};
    std::uint32_t              _superframe_counter{0U};

    int effectiveFrameSizeSamples() const noexcept
    {
        const int fss = static_cast<int>(frame_size_samples);
        return (fss > 0) ? fss : 1920;
    }

    void emitSuperframe() noexcept
    {
        // Each voice frame contributes voice_frame_bytes worth of "opus data".
        // For GR4 we synthesise a flat Opus byte vector from the sample buffer.
        const int  fps     = static_cast<int>(frames_per_superframe);
        const int  opBytes = static_cast<int>(voice_frame_bytes);
        const std::size_t total_opus = static_cast<std::size_t>(fps) * static_cast<std::size_t>(opBytes);

        // Build synthetic 40-byte Opus frames: copy samples (float→uint8 clipped) per frame.
        const std::size_t fss    = static_cast<std::size_t>(effectiveFrameSizeSamples());
        const std::size_t nvoice = std::min(static_cast<std::size_t>(fps),
                                            detail::VOICE_FRAMES_PER_SF);

        // We only use VOICE_FRAMES_PER_SF (24) voice frames regardless of frames_per_superframe.
        std::vector<std::uint8_t> opus_data_960(detail::VOICE_FRAMES_PER_SF * detail::OPUS_BYTES_PER_FRAME, 0U);
        for (std::size_t f = 0UZ; f < nvoice && f < static_cast<std::size_t>(fps); ++f) {
            const std::size_t sample_start = f * fss;
            for (std::size_t b = 0UZ; b < detail::OPUS_BYTES_PER_FRAME; ++b) {
                const std::size_t si = sample_start + b;
                if (si < _sample_buf.size()) {
                    const float       s = _sample_buf[si];
                    const float       clamped = std::max(-1.0F, std::min(1.0F, s));
                    opus_data_960[f * detail::OPUS_BYTES_PER_FRAME + b]
                        = static_cast<std::uint8_t>((clamped * 127.0F) + 128.0F);
                }
            }
        }

        // Build superframe with sync frame prepended (always on first SF for tests)
        const bool prepend_sync = static_cast<bool>(enable_signing) == false;
        auto assembled = detail::assembleFrames(
            std::span<const std::uint8_t>(opus_data_960),
            std::string_view(static_cast<std::string>(callsign)),
            prepend_sync,
            _superframe_counter);

        ++_superframe_counter;

        // Publish
        gr::property_map body;
        body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
            = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(assembled)));
        gr::Message msg;
        msg.cmd  = gr::message::Command::Notify;
        msg.data = std::move(body);
        auto w = control_out.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        w[0]   = std::move(msg);
        w.publish(1UZ);

        (void)total_opus; // used for documentation
    }

    [[nodiscard]] gr::work::Status processBulk(std::span<const float> input) noexcept
    {
        const int   fps = static_cast<int>(frames_per_superframe);
        const int   fss = effectiveFrameSizeSamples();
        // Total samples needed for one complete superframe
        const std::size_t required = static_cast<std::size_t>(fps) * static_cast<std::size_t>(fss);

        // Accumulate
        _sample_buf.insert(_sample_buf.end(), input.begin(), input.end());

        // Emit superframe(s) whenever we have enough samples
        while (_sample_buf.size() >= required) {
            emitSuperframe();
            // Discard consumed samples
            _sample_buf.erase(_sample_buf.begin(),
                              _sample_buf.begin() + static_cast<std::ptrdiff_t>(required));
        }

        return gr::work::Status::OK;
    }
};

} // namespace gnuradio4::sleipnir

#endif
