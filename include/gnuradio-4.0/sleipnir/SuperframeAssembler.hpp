// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_SLEIPNIR_SUPERFRAMEASSEMBLER_HPP
#define GNURADIO4_SLEIPNIR_SUPERFRAMEASSEMBLER_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/annotated.hpp>
#include <gnuradio-4.0/sleipnir/detail/SleipnirFrameFormat.hpp>
#include <gnuradio-4.0/sleipnir/detail/TextFrameFormat.hpp>

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace gnuradio4::sleipnir {

GR_REGISTER_BLOCK(gnuradio4::sleipnir::SuperframeAssembler)

/**
 * SuperframeAssembler — pure message-to-message block (no stream ports).
 *
 * Input  (opus_frames_in):  gr::Message carrying pdu_bytes Tensor<uint8_t> of
 *                           24 x 40 = 960 bytes of concatenated Opus frames.
 * Output (superframe_out):  gr::Message carrying pdu_bytes Tensor<uint8_t>
 *                           of assembled frame payloads (N x 49 bytes).
 *
 * When enable_sync_frames is true, a 49-byte sync frame (carrying SYNC_PATTERN
 * 0xDEADBEEFCAFEBABE) is prepended to every superframe that falls on a
 * sync_frame_interval boundary (superframe_counter % sync_frame_interval == 0).
 * The result then has 25 x 49 = 1225 bytes; non-sync superframes have
 * 24 x 49 = 1176 bytes.
 *
 * Without signing the output never contains an auth/signature frame.
 * With enable_signing=true the first frame (64 bytes) is a signature placeholder
 * (only filled when GR_SLEIPNIR4_HAVE_OPENSSL is defined and private_key_path
 * points to a valid PEM key).
 *
 * When `text_frame_in` receives 64-byte TEXT frame PDUs before the next
 * `opus_frames_in` cycle, they are concatenated and appended after all
 * 49-byte voice/sync frames with a `TEXT` trailer (see `detail::append_text_trailer`).
 */
struct SuperframeAssembler : gr::Block<SuperframeAssembler> {
    using Description = gr::Doc<"Assemble Opus PDU (24x40 bytes) into superframe PDU (N x 49 bytes) with optional sync frames.">;

    gr::MsgPortIn  opus_frames_in{};
    gr::MsgPortIn  text_frame_in{};
    gr::MsgPortOut superframe_out{};

    gr::Annotated<std::string, "callsign",            gr::Doc<"Station callsign embedded in voice frames">>         callsign            = std::string("N0CALL");
    gr::Annotated<bool,        "enable_signing",       gr::Doc<"Prepend ECDSA auth frame (requires OpenSSL)">>      enable_signing      = false;
    gr::Annotated<std::string, "private_key_path",     gr::Doc<"Path to PEM private key for signing">>               private_key_path    = std::string("");
    gr::Annotated<bool,        "enable_sync_frames",   gr::Doc<"Insert sync frames at sync_frame_interval">>        enable_sync_frames  = true;
    gr::Annotated<int,         "sync_frame_interval",  gr::Doc<"Insert sync frame every N superframes (0=never)">>  sync_frame_interval = 5;

    GR_MAKE_REFLECTABLE(SuperframeAssembler, opus_frames_in, text_frame_in, superframe_out,
                        callsign, enable_signing, private_key_path,
                        enable_sync_frames, sync_frame_interval);

    std::uint32_t                 _superframe_counter{0U};
    std::vector<std::uint8_t>     _queued_text_concat{};

    void publishSuperframe(std::vector<std::uint8_t> payload) noexcept
    {
        gr::property_map body;
        body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
            = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(payload)));
        gr::Message msg;
        msg.cmd  = gr::message::Command::Notify;
        msg.data = std::move(body);
        auto w = superframe_out.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        w[0]   = std::move(msg);
        w.publish(1UZ);
    }

    // Called directly in tests (and via processMessages in production).
    void handleOpusFramesPdu(gr::Message msg) noexcept
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
        std::span<const std::uint8_t> opus_data(tensor->data(), tensor->size());

        // Determine whether to prepend a sync frame.
        const int  interval     = static_cast<bool>(enable_sync_frames) ? static_cast<int>(sync_frame_interval) : 0;
        const bool prepend_sync = (enable_sync_frames && interval > 0
                                   && (_superframe_counter % static_cast<std::uint32_t>(interval) == 0U));

        auto assembled = detail::assembleFrames(
            opus_data,
            std::string_view(static_cast<std::string>(callsign)),
            prepend_sync,
            _superframe_counter);

        if (!_queued_text_concat.empty()) {
            assembled = detail::append_text_trailer(std::move(assembled), std::span<const std::uint8_t>(_queued_text_concat));
            _queued_text_concat.clear();
        }

        ++_superframe_counter;
        publishSuperframe(std::move(assembled));
    }

    void handleTextFramePdu(gr::Message msg) noexcept
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
        if (tensor == nullptr || tensor->size() < detail::TEXT_FRAME_SIZE) {
            return;
        }
        const std::span<const std::uint8_t> tf(tensor->data(), detail::TEXT_FRAME_SIZE);
        _queued_text_concat.insert(_queued_text_concat.end(), tf.begin(), tf.end());
    }

    // GR4 scheduler calls this when messages arrive on any input message port.
    void processMessages(gr::MsgPortIn& port, gr::Message msg) noexcept
    {
        if (&port == &opus_frames_in) {
            handleOpusFramesPdu(std::move(msg));
        } else {
            handleTextFramePdu(std::move(msg));
        }
    }
};

} // namespace gnuradio4::sleipnir

#endif
