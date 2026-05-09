// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_SLEIPNIR_SUPERFRAMEPARSER_HPP
#define GNURADIO4_SLEIPNIR_SUPERFRAMEPARSER_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/annotated.hpp>
#include <gnuradio-4.0/sleipnir/detail/SleipnirFrameFormat.hpp>
#include <gnuradio-4.0/sleipnir/detail/TextFrameFormat.hpp>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <string>
#include <vector>

namespace gnuradio4::sleipnir {

GR_REGISTER_BLOCK(gnuradio4::sleipnir::SuperframeParser)

/**
 * SuperframeParser — pure message-to-message block (no stream ports).
 *
 * Input  (ldpc_decoded_in): gr::Message with pdu_bytes (49-byte-aligned voice/sync
 *                           payloads, optional TEXT trailer).
 * Output (opus_frames_out): recovered Opus data (voice frames).
 * Output (status_out): fer (float), frame_errors, total_frames, sync_detected.
 * Output (text_frame_out): emits one message per appended 64-byte TEXT frame chunk.
 *
 * Frame error rate tracking:
 *   frame_error_count       — cumulative count of frames that failed to decode
 *   total_frames_received   — cumulative count of all frames processed
 *   FER = frame_error_count / total_frames_received
 */
struct SuperframeParser : gr::Block<SuperframeParser> {
    using Description = gr::Doc<"Parse superframe PDU (N x 49 bytes) into Opus PDU and status.">;

    gr::MsgPortIn  ldpc_decoded_in{};
    gr::MsgPortOut opus_frames_out{};
    gr::MsgPortOut status_out{};
    gr::MsgPortOut text_frame_out{};

    gr::Annotated<std::string,             "local_callsign",       gr::Doc<"This station callsign">>                     local_callsign       = std::string("N0CALL");
    gr::Annotated<bool,                    "require_signatures",   gr::Doc<"Reject superframes without valid signatures">> require_signatures   = false;
    gr::Annotated<bool,                    "enable_sync_detection", gr::Doc<"Look for sync frames and update sync state">> enable_sync_detection = true;
    gr::Annotated<gr::Tensor<std::uint8_t>,"mac_key",              gr::Doc<"32-byte MAC key (empty = no MAC check)">>    mac_key              = gr::Tensor<std::uint8_t>{};

    // Read-only counters exposed as reflected settings for FER monitoring.
    gr::Annotated<gr::Size_t, "frame_error_count",      gr::Doc<"Cumulative frame error count">>     frame_error_count     = gr::Size_t{0U};
    gr::Annotated<gr::Size_t, "total_frames_received",  gr::Doc<"Cumulative total frames received">> total_frames_received = gr::Size_t{0U};

    GR_MAKE_REFLECTABLE(SuperframeParser, ldpc_decoded_in, opus_frames_out, status_out, text_frame_out,
                        local_callsign, require_signatures, enable_sync_detection, mac_key,
                        frame_error_count, total_frames_received);

    bool _sync_detected{false};

    void publishOpusFrames(std::vector<std::uint8_t> payload) noexcept
    {
        gr::property_map body;
        body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
            = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(payload)));
        gr::Message msg;
        msg.cmd  = gr::message::Command::Notify;
        msg.data = std::move(body);
        auto w = opus_frames_out.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        w[0]   = std::move(msg);
        w.publish(1UZ);
    }

    void publishStatus(float fer, gr::Size_t errors, gr::Size_t total, bool sync) noexcept
    {
        gr::property_map body;
        body[gr::convert_string_domain(std::string_view("fer"))]           = gr::pmt::Value(fer);
        body[gr::convert_string_domain(std::string_view("frame_errors"))]  = gr::pmt::Value(errors);
        body[gr::convert_string_domain(std::string_view("total_frames"))]  = gr::pmt::Value(total);
        body[gr::convert_string_domain(std::string_view("sync_detected"))] = gr::pmt::Value(sync);
        gr::Message msg;
        msg.cmd  = gr::message::Command::Notify;
        msg.data = std::move(body);
        auto w = status_out.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        w[0]   = std::move(msg);
        w.publish(1UZ);
    }

    void publishTextFrame(std::array<std::uint8_t, detail::TEXT_FRAME_SIZE> frm) noexcept
    {
        gr::property_map body;
        body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
            = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::vector<std::uint8_t>(frm.begin(), frm.end())));
        gr::Message msg;
        msg.cmd  = gr::message::Command::Notify;
        msg.data = std::move(body);
        auto w = text_frame_out.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        w[0]   = std::move(msg);
        w.publish(1UZ);
    }

    // Called directly in tests and via processMessages in production.
    void handleLdpcDecodedPdu(gr::Message msg) noexcept
    {
        if (!msg.data.has_value()) {
            return;
        }
        const auto& body = msg.data.value();
        const auto  key  = gr::convert_string_domain(std::string_view("pdu_bytes"));
        const auto  it   = body.find(key);
        if (it == body.end()) {
            return;
        }
        const auto* tensor = it->second.get_if<gr::Tensor<std::uint8_t>>();
        if (tensor == nullptr) {
            return;
        }

        std::span<const std::uint8_t> raw(tensor->data(), tensor->size());

        std::span<const std::uint8_t> voice_part{};
        std::span<const std::uint8_t> text_part{};
        detail::split_voice_and_text_trailer(raw, &voice_part, &text_part);

        const std::size_t frame_sz = detail::VOICE_FRAME_SIZE; // 49

        if (voice_part.empty()) {
            return;
        }

        if (voice_part.size() % frame_sz != 0UZ) {
            return;
        }

        const std::size_t total_in_frames = voice_part.size() / frame_sz;

        // Walk frames, detect sync, collect Opus bytes
        std::vector<std::uint8_t> opus_out;
        opus_out.reserve(total_in_frames * detail::OPUS_STORED_BYTES);

        std::size_t errors_this_call = 0UZ;
        bool        sync_this_call   = false;

        for (std::size_t fi = 0UZ; fi < total_in_frames; ++fi) {
            std::span<const std::uint8_t> frame = voice_part.subspan(fi * frame_sz, frame_sz);

            // Detect sync frame
            if (enable_sync_detection && detail::isSyncFrame(frame)) {
                sync_this_call   = true;
                _sync_detected   = true;
                ++total_frames_received;
                // Sync frames do not contribute to Opus output but are not errors.
                continue;
            }

            ++total_frames_received;

            // Basic validity check: first byte must be FRAME_TYPE_VOICE
            if (frame[0] != detail::FRAME_TYPE_VOICE) {
                ++frame_error_count;
                ++errors_this_call;
                continue;
            }

            // Extract stored Opus bytes (bytes 1-39)
            for (std::size_t b = 1UZ; b <= detail::OPUS_STORED_BYTES; ++b) {
                opus_out.push_back(frame[b]);
            }
        }

        const float fer = (static_cast<gr::Size_t>(total_frames_received) > gr::Size_t{0U})
            ? static_cast<float>(static_cast<gr::Size_t>(frame_error_count))
                / static_cast<float>(static_cast<gr::Size_t>(total_frames_received))
            : 0.0F;

        publishStatus(fer,
                      static_cast<gr::Size_t>(frame_error_count),
                      static_cast<gr::Size_t>(total_frames_received),
                      sync_this_call || _sync_detected);

        if (!opus_out.empty()) {
            publishOpusFrames(std::move(opus_out));
        }

        if (!text_part.empty() && text_part.size() % detail::TEXT_FRAME_SIZE == 0UZ) {
            const std::size_t n_tf = text_part.size() / detail::TEXT_FRAME_SIZE;
            for (std::size_t ti = 0UZ; ti < n_tf; ++ti) {
                std::span<const std::uint8_t> blk = text_part.subspan(ti * detail::TEXT_FRAME_SIZE, detail::TEXT_FRAME_SIZE);
                std::array<std::uint8_t, detail::TEXT_FRAME_SIZE> arr{};
                std::memcpy(arr.data(), blk.data(), detail::TEXT_FRAME_SIZE);
                publishTextFrame(arr);
            }
        }
    }

    void processMessages(gr::MsgPortIn& /*port*/, gr::Message msg) noexcept
    {
        handleLdpcDecodedPdu(std::move(msg));
    }
};

} // namespace gnuradio4::sleipnir

#endif
