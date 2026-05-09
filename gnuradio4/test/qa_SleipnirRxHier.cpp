// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>

#include <gnuradio-4.0/sleipnir/SleipnirRxHier.hpp>
#include <gnuradio-4.0/sleipnir/detail/SleipnirFrameFormat.hpp>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

using namespace boost::ut;
using namespace gnuradio4::sleipnir;
namespace sleipnir_detail = gnuradio4::sleipnir::detail;

namespace {

gr::Message makeDecodedPdu(std::vector<std::uint8_t> data)
{
    gr::property_map body;
    body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
        = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(data)));
    gr::Message msg;
    msg.cmd  = gr::message::Command::Notify;
    msg.data = std::move(body);
    return msg;
}

bool readStatusFromSink(gr::MsgPortIn& sink, float& fer_out, bool& sync_out,
                        gr::Size_t& errors_out, gr::Size_t& total_out)
{
    if (sink.streamReader().available() < 1UZ) {
        return false;
    }
    auto               span = sink.streamReader().template get<gr::SpanReleasePolicy::ProcessAll>(1UZ);
    const gr::Message& msg  = span[0UZ];
    if (!msg.data.has_value()) {
        return false;
    }
    const auto& body = msg.data.value();

    auto getFloat = [&](std::string_view k) -> float {
        const auto it = body.find(gr::convert_string_domain(k));
        if (it == body.end()) {
            return 0.0F;
        }
        if (const auto* v = it->second.get_if<float>()) {
            return *v;
        }
        return 0.0F;
    };
    auto getBool = [&](std::string_view k) -> bool {
        const auto it = body.find(gr::convert_string_domain(k));
        if (it == body.end()) {
            return false;
        }
        if (const auto* v = it->second.get_if<bool>()) {
            return *v;
        }
        return false;
    };
    auto getSize = [&](std::string_view k) -> gr::Size_t {
        const auto it = body.find(gr::convert_string_domain(k));
        if (it == body.end()) {
            return gr::Size_t{0U};
        }
        if (const auto* v = it->second.get_if<gr::Size_t>()) {
            return *v;
        }
        return gr::Size_t{0U};
    };

    fer_out    = getFloat("fer");
    sync_out   = getBool("sync_detected");
    errors_out = getSize("frame_errors");
    total_out  = getSize("total_frames");
    return true;
}

// Build N valid voice frames (FRAME_TYPE_VOICE=0x00 at byte 0, non-zero data).
std::vector<std::uint8_t> buildValidFrames(std::size_t n_frames, std::uint8_t fill = 0x55U)
{
    std::vector<std::uint8_t> buf(n_frames * sleipnir_detail::VOICE_FRAME_SIZE, fill);
    for (std::size_t f = 0UZ; f < n_frames; ++f) {
        buf[f * sleipnir_detail::VOICE_FRAME_SIZE] = sleipnir_detail::FRAME_TYPE_VOICE; // byte 0 = voice type
    }
    return buf;
}

} // namespace

const suite<"SleipnirRxHier"> SleipnirRxHierSuite = [] {

    "outputs_silence_when_no_valid_frame_received"_test = [] {
        SleipnirRxHier rx{gr::property_map{
            {"name", std::string("rx_silence")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false}}};
        rx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn status_sink;
        expect(rx.status_out.connect(status_sink).has_value());

        // No message fed — internal audio buffer must be empty.
        expect(rx._audio_buf.empty()) << "audio buffer must be empty before any message";
        // No status should have been published.
        expect(status_sink.streamReader().available() == 0UZ)
            << "no status should be present before any message is processed";
    };

    "after_valid_ldpc_decoded_message_outputs_audio_samples"_test = [] {
        SleipnirRxHier rx{gr::property_map{
            {"name", std::string("rx_audio")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false}}};
        rx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn status_sink;
        expect(rx.status_out.connect(status_sink).has_value());

        // Feed a valid superframe (3 voice frames with non-zero data)
        auto frames = buildValidFrames(3UZ, 0xC0U);
        rx.handleLdpcDecodedPdu(makeDecodedPdu(frames));

        // The block should have queued audio samples internally.
        // Verify by checking that a status message was emitted.
        float      fer   = 0.0F;
        bool       sync  = false;
        gr::Size_t errs  = gr::Size_t{0U};
        gr::Size_t total = gr::Size_t{0U};
        expect(readStatusFromSink(status_sink, fer, sync, errs, total))
            << "status_out message expected after receiving LDPC decoded PDU";
        expect(static_cast<std::size_t>(total) == 3UZ)
            << "expected 3 total frames received";
    };

    "status_out_emitted_with_correct_fer_fields"_test = [] {
        SleipnirRxHier rx{gr::property_map{
            {"name", std::string("rx_fer")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false}}};
        rx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn status_sink;
        expect(rx.status_out.connect(status_sink).has_value());

        // 2 valid frames + 2 corrupted frames
        std::vector<std::uint8_t> mixed;
        auto valid = buildValidFrames(2UZ, 0x01U);
        mixed.insert(mixed.end(), valid.begin(), valid.end());
        // Append 2 frames with type != FRAME_TYPE_VOICE and not sync pattern
        std::vector<std::uint8_t> bad(2UZ * sleipnir_detail::VOICE_FRAME_SIZE, 0x42U);
        mixed.insert(mixed.end(), bad.begin(), bad.end());

        rx.handleLdpcDecodedPdu(makeDecodedPdu(mixed));

        float      fer   = 0.0F;
        bool       sync  = false;
        gr::Size_t errs  = gr::Size_t{0U};
        gr::Size_t total = gr::Size_t{0U};
        expect(readStatusFromSink(status_sink, fer, sync, errs, total));
        expect(static_cast<std::size_t>(total) == 4UZ) << "total_frames must be 4";
        expect(static_cast<std::size_t>(errs) == 2UZ)  << "frame_errors must be 2";
        // FER = 2/4 = 0.5
        expect(fer > 0.45F && fer < 0.55F)
            << "FER should be 0.5 but got " << fer;
    };

    "status_out_sync_detected_true_when_sync_frame_present"_test = [] {
        SleipnirRxHier rx{gr::property_map{
            {"name", std::string("rx_sync")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false}}};
        rx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn status_sink;
        expect(rx.status_out.connect(status_sink).has_value());

        // Build payload with a sync frame followed by one voice frame
        auto sync_frame = sleipnir_detail::buildSyncFrame(0U);
        std::vector<std::uint8_t> payload(sync_frame.begin(), sync_frame.end());
        auto vf = sleipnir_detail::buildVoiceFrame(
            std::span<const std::uint8_t>(std::vector<std::uint8_t>(40U, 0xAAU)),
            1);
        payload.insert(payload.end(), vf.begin(), vf.end());

        rx.handleLdpcDecodedPdu(makeDecodedPdu(payload));

        float      fer   = 0.0F;
        bool       sync  = false;
        gr::Size_t errs  = gr::Size_t{0U};
        gr::Size_t total = gr::Size_t{0U};
        expect(readStatusFromSink(status_sink, fer, sync, errs, total));
        expect(sync) << "sync_detected must be true when sync frame is in the payload";
    };

    "zero_fer_when_all_frames_valid"_test = [] {
        SleipnirRxHier rx{gr::property_map{
            {"name", std::string("rx_zero_fer")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false}}};
        rx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn status_sink;
        expect(rx.status_out.connect(status_sink).has_value());

        auto frames = buildValidFrames(5UZ, 0x11U);
        rx.handleLdpcDecodedPdu(makeDecodedPdu(frames));

        float      fer   = 1.0F;
        bool       sync  = false;
        gr::Size_t errs  = gr::Size_t{1U};
        gr::Size_t total = gr::Size_t{0U};
        expect(readStatusFromSink(status_sink, fer, sync, errs, total));
        expect(static_cast<std::size_t>(errs) == 0UZ) << "no frame errors expected";
        expect(fer < 0.001F) << "FER must be 0.0 when all frames are valid";
    };
};

int main()
{
    return boost::ut::cfg<boost::ut::override>.run();
}
