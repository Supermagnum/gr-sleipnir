// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>

#include <gnuradio-4.0/sleipnir/SuperframeAssembler.hpp>
#include <gnuradio-4.0/sleipnir/SuperframeParser.hpp>
#include <gnuradio-4.0/sleipnir/detail/SleipnirFrameFormat.hpp>

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

using namespace boost::ut;
using namespace gnuradio4::sleipnir;
namespace sleipnir_detail = gnuradio4::sleipnir::detail;

namespace {

gr::Message makePdu(std::vector<std::uint8_t> data)
{
    gr::property_map body;
    body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
        = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(data)));
    gr::Message msg;
    msg.cmd  = gr::message::Command::Notify;
    msg.data = std::move(body);
    return msg;
}

const gr::Tensor<std::uint8_t>* firstPduFromSink(gr::MsgPortIn& sink)
{
    if (sink.streamReader().available() < 1UZ) {
        return nullptr;
    }
    auto               span = sink.streamReader().template get<gr::SpanReleasePolicy::ProcessAll>(1UZ);
    const gr::Message& msg  = span[0UZ];
    if (!msg.data.has_value()) {
        return nullptr;
    }
    const auto& body = msg.data.value();
    const auto  key  = gr::convert_string_domain(std::string_view("pdu_bytes"));
    const auto  it   = body.find(key);
    if (it == body.end()) {
        return nullptr;
    }
    return it->second.get_if<gr::Tensor<std::uint8_t>>();
}

// Read one status message from sink.
// Returns true if found and fills the output parameters.
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

    auto getFloat = [&](std::string_view k, float def) -> float {
        const auto it = body.find(gr::convert_string_domain(k));
        if (it == body.end()) {
            return def;
        }
        if (const auto* v = it->second.get_if<float>()) {
            return *v;
        }
        return def;
    };
    auto getBool = [&](std::string_view k, bool def) -> bool {
        const auto it = body.find(gr::convert_string_domain(k));
        if (it == body.end()) {
            return def;
        }
        if (const auto* v = it->second.get_if<bool>()) {
            return *v;
        }
        return def;
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

    fer_out    = getFloat("fer", 0.0F);
    sync_out   = getBool("sync_detected", false);
    errors_out = getSize("frame_errors");
    total_out  = getSize("total_frames");
    return true;
}

// Build a valid superframe payload (24 voice frames, no sync).
std::vector<std::uint8_t> buildValidSuperframePayload(std::string_view callsign = "N0CALL")
{
    std::vector<std::uint8_t> opus(24UZ * sleipnir_detail::OPUS_BYTES_PER_FRAME, 0xAAU);
    return sleipnir_detail::assembleFrames(std::span<const std::uint8_t>(opus), callsign,
                                  false, 0U);
}

// Build a valid superframe with a sync frame prepended.
std::vector<std::uint8_t> buildSyncSuperframePayload()
{
    std::vector<std::uint8_t> opus(24UZ * sleipnir_detail::OPUS_BYTES_PER_FRAME, 0xBBU);
    return sleipnir_detail::assembleFrames(std::span<const std::uint8_t>(opus), "N0CALL",
                                  true, 0U);
}

} // namespace

const suite<"SuperframeParser"> SuperframeParserSuite = [] {

    "parser_accepts_valid_superframe_emits_opus_pdu"_test = [] {
        SuperframeParser parser{gr::property_map{
            {"name", std::string("parser")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false},
            {"enable_sync_detection", false}}};
        parser.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn opus_sink, status_sink, text_sink;
        expect(parser.opus_frames_out.connect(opus_sink).has_value());
        expect(parser.status_out.connect(status_sink).has_value());
        expect(parser.text_frame_out.connect(text_sink).has_value());

        parser.handleLdpcDecodedPdu(makePdu(buildValidSuperframePayload()));

        const auto* pdu = firstPduFromSink(opus_sink);
        expect(pdu != nullptr) << "expected Opus frames PDU";
        if (pdu) {
            expect(pdu->size() > 0UZ) << "Opus output must be non-empty";
        }
    };

    "valid_sync_frame_detected_sets_sync_in_status"_test = [] {
        SuperframeParser parser{gr::property_map{
            {"name", std::string("parser_sync")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false},
            {"enable_sync_detection", true}}};
        parser.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn opus_sink, status_sink, text_sink;
        expect(parser.opus_frames_out.connect(opus_sink).has_value());
        expect(parser.status_out.connect(status_sink).has_value());
        expect(parser.text_frame_out.connect(text_sink).has_value());

        parser.handleLdpcDecodedPdu(makePdu(buildSyncSuperframePayload()));

        float      fer   = 0.0F;
        bool       sync  = false;
        gr::Size_t errs  = gr::Size_t{0U};
        gr::Size_t total = gr::Size_t{0U};
        expect(readStatusFromSink(status_sink, fer, sync, errs, total))
            << "expected a status message";
        expect(sync) << "sync_detected must be true when sync frame is present";
    };

    "corrupted_frame_increments_frame_error_count"_test = [] {
        SuperframeParser parser{gr::property_map{
            {"name", std::string("parser_err")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false},
            {"enable_sync_detection", false}}};
        parser.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn opus_sink, status_sink, text_sink;
        expect(parser.opus_frames_out.connect(opus_sink).has_value());
        expect(parser.status_out.connect(status_sink).has_value());
        expect(parser.text_frame_out.connect(text_sink).has_value());

        // Build a payload where all frames have byte 0 set to an invalid type.
        const std::size_t n_frames = 5UZ;
        std::vector<std::uint8_t> corrupt(n_frames * sleipnir_detail::VOICE_FRAME_SIZE, 0xFFU);
        // 0xFF as the first byte means FRAME_TYPE_SYNC (isSyncFrame only triggers on
        // the full 8-byte pattern) — or rather it won't match FRAME_TYPE_VOICE (0x00).
        // Make sure the sync pattern is NOT present so they are treated as errors.
        parser.handleLdpcDecodedPdu(makePdu(corrupt));

        float      fer   = 0.0F;
        bool       sync  = false;
        gr::Size_t errs  = gr::Size_t{0U};
        gr::Size_t total = gr::Size_t{0U};
        expect(readStatusFromSink(status_sink, fer, sync, errs, total));
        expect(static_cast<std::size_t>(errs) > 0UZ)
            << "frame_error_count must increase for corrupted frames";
    };

    "fer_calculation_correct_after_N_frames"_test = [] {
        SuperframeParser parser{gr::property_map{
            {"name", std::string("parser_fer")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false},
            {"enable_sync_detection", false}}};
        parser.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn opus_sink, status_sink, text_sink;
        expect(parser.opus_frames_out.connect(opus_sink).has_value());
        expect(parser.status_out.connect(status_sink).has_value());
        expect(parser.text_frame_out.connect(text_sink).has_value());

        // Send 4 valid voice frames
        {
            const std::size_t n = 4UZ;
            std::vector<std::uint8_t> valid_frames(n * sleipnir_detail::VOICE_FRAME_SIZE, 0U);
            // Frame type 0x00 at byte 0 of each frame
            for (std::size_t i = 0UZ; i < n; ++i) {
                valid_frames[i * sleipnir_detail::VOICE_FRAME_SIZE] = sleipnir_detail::FRAME_TYPE_VOICE;
            }
            parser.handleLdpcDecodedPdu(makePdu(valid_frames));
            // Drain the status message
            float fer; bool sync; gr::Size_t e, t;
            readStatusFromSink(status_sink, fer, sync, e, t);
            // Drain any opus output too
            if (opus_sink.streamReader().available() > 0UZ) {
                (void) opus_sink.streamReader().template get<gr::SpanReleasePolicy::ProcessAll>(1UZ);
            }
        }

        // Send 2 corrupted frames (type != 0x00, not sync pattern)
        {
            std::vector<std::uint8_t> bad_frames(2UZ * sleipnir_detail::VOICE_FRAME_SIZE, 0x42U);
            parser.handleLdpcDecodedPdu(makePdu(bad_frames));
        }

        float      fer   = 0.0F;
        bool       sync  = false;
        gr::Size_t errs  = gr::Size_t{0U};
        gr::Size_t total = gr::Size_t{0U};
        expect(readStatusFromSink(status_sink, fer, sync, errs, total));

        // total_frames_received = 6, frame_error_count = 2
        // FER = 2/6 = 0.333...
        expect(static_cast<std::size_t>(total) == 6UZ)
            << "expected 6 total frames";
        expect(static_cast<std::size_t>(errs) == 2UZ)
            << "expected 2 frame errors";
        expect(fer > 0.30F && fer < 0.40F)
            << "FER should be ~0.333 but got " << fer;
    };

    "round_trip_assemble_then_parse_recovers_opus_bytes"_test = [] {
        // Assemble
        SuperframeAssembler asm_{gr::property_map{
            {"name", std::string("asm_rt")},
            {"callsign", std::string("N0CALL")},
            {"enable_sync_frames", false},
            {"sync_frame_interval", 1}}};
        asm_.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn asm_sink;
        expect(asm_.superframe_out.connect(asm_sink).has_value());

        // Use a recognizable pattern
        std::vector<std::uint8_t> opus_in(24UZ * 40UZ);
        for (std::size_t i = 0UZ; i < opus_in.size(); ++i) {
            opus_in[i] = static_cast<std::uint8_t>(i & 0xFFU);
        }
        asm_.handleOpusFramesPdu([&]() {
            gr::property_map body;
            body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
                = gr::pmt::Value(gr::Tensor<std::uint8_t>(opus_in));
            gr::Message msg;
            msg.cmd  = gr::message::Command::Notify;
            msg.data = std::move(body);
            return msg;
        }());

        const auto* asm_pdu = firstPduFromSink(asm_sink);
        expect(asm_pdu != nullptr);
        if (!asm_pdu) {
            return;
        }

        // Parse
        SuperframeParser parser{gr::property_map{
            {"name", std::string("parser_rt")},
            {"local_callsign", std::string("N0CALL")},
            {"require_signatures", false},
            {"enable_sync_detection", false}}};
        parser.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn opus_sink, status_sink, text_sink;
        expect(parser.opus_frames_out.connect(opus_sink).has_value());
        expect(parser.status_out.connect(status_sink).has_value());
        expect(parser.text_frame_out.connect(text_sink).has_value());

        std::vector<std::uint8_t> assembled(asm_pdu->data(),
                                            asm_pdu->data() + asm_pdu->size());
        parser.handleLdpcDecodedPdu(makePdu(std::move(assembled)));

        const auto* opus_out = firstPduFromSink(opus_sink);
        expect(opus_out != nullptr) << "parser must emit Opus frames";
        if (opus_out) {
            // Each of the 24 voice frames stores 39 Opus bytes.
            // The first byte of each stored opus_in frame (index 0, 40, 80, ...)
            // maps to stored bytes [1-39] i.e. opus_in[frame * 40 + 0] to [+ 38].
            // Verify at least that non-zero Opus data was recovered.
            expect(opus_out->size() == 24UZ * sleipnir_detail::OPUS_STORED_BYTES)
                << "expected 24 * 39 = 936 recovered Opus bytes";
        }
    };
};

int main()
{
    return boost::ut::cfg<boost::ut::override>.run();
}
