// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>

#include <gnuradio-4.0/sleipnir/SuperframeAssembler.hpp>
#include <gnuradio-4.0/sleipnir/detail/SleipnirFrameFormat.hpp>

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

using namespace boost::ut;
using namespace gnuradio4::sleipnir;
namespace sleipnir_detail = gnuradio4::sleipnir::detail;

namespace {

// Build a gr::Message containing a pdu_bytes tensor with opus_data.
gr::Message makeOpusPdu(std::vector<std::uint8_t> opus_data)
{
    gr::property_map body;
    body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
        = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(opus_data)));
    gr::Message msg;
    msg.cmd  = gr::message::Command::Notify;
    msg.data = std::move(body);
    return msg;
}

// Read one message from a connected sink port.
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

} // namespace

const suite<"SuperframeAssembler"> SuperframeAssemblerSuite = [] {

    "accepts_24x40_opus_pdu_and_emits_superframe"_test = [] {
        SuperframeAssembler asm_{gr::property_map{
            {"name", std::string("asm")},
            {"callsign", std::string("N0CALL")},
            {"enable_sync_frames", false},
            {"sync_frame_interval", 1}}};
        asm_.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(asm_.superframe_out.connect(sink).has_value());

        std::vector<std::uint8_t> opus(24UZ * 40UZ, 0xAAU);
        asm_.handleOpusFramesPdu(makeOpusPdu(std::move(opus)));

        const auto* pdu = firstPduFromSink(sink);
        expect(pdu != nullptr) << "expected a superframe PDU on output";
        if (pdu) {
            expect(pdu->size() > 0UZ) << "superframe PDU must be non-empty";
        }
    };

    "output_has_25_frames_at_sync_interval"_test = [] {
        // With sync_frame_interval=1 and enable_sync_frames=true every call
        // emits a sync frame prepended to 24 voice frames → 25 * 49 bytes.
        SuperframeAssembler asm_{gr::property_map{
            {"name", std::string("asm_sync")},
            {"callsign", std::string("N0CALL")},
            {"enable_sync_frames", true},
            {"sync_frame_interval", 1}}};
        asm_.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(asm_.superframe_out.connect(sink).has_value());

        std::vector<std::uint8_t> opus(24UZ * 40UZ, 0x00U);
        asm_.handleOpusFramesPdu(makeOpusPdu(opus));

        const auto* pdu = firstPduFromSink(sink);
        expect(pdu != nullptr);
        if (pdu) {
            constexpr std::size_t expected_bytes
                = 25UZ * sleipnir_detail::VOICE_FRAME_SIZE; // 25 * 49 = 1225
            expect(pdu->size() == expected_bytes)
                << "expected 25 frames (" << expected_bytes << " bytes), got " << pdu->size();
        }
    };

    "sync_frame_inserted_at_correct_interval"_test = [] {
        // With sync_frame_interval=3:
        //  call 0 (counter=0): 0 % 3 == 0 → sync frame → 1225 bytes
        //  call 1 (counter=1): no sync → 24 * 49 = 1176 bytes
        //  call 2 (counter=2): no sync → 1176 bytes
        //  call 3 (counter=3): 3 % 3 == 0 → sync → 1225 bytes
        SuperframeAssembler asm_{gr::property_map{
            {"name", std::string("asm_interval")},
            {"callsign", std::string("N0CALL")},
            {"enable_sync_frames", true},
            {"sync_frame_interval", 3}}};
        asm_.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink0, sink1, sink2, sink3;
        expect(asm_.superframe_out.connect(sink0).has_value());

        std::vector<std::uint8_t> opus(24UZ * 40UZ, 0x00U);

        // Call 0 → sync
        asm_.handleOpusFramesPdu(makeOpusPdu(opus));
        {
            const auto* p = firstPduFromSink(sink0);
            expect(p != nullptr);
            if (p) {
                expect(p->size() == 25UZ * sleipnir_detail::VOICE_FRAME_SIZE)
                    << "call 0 should have sync frame";
            }
        }

        // Reconnect for next read
        gr::MsgPortIn sinkA;
        expect(asm_.superframe_out.connect(sinkA).has_value());
        // Call 1 → no sync
        asm_.handleOpusFramesPdu(makeOpusPdu(opus));
        {
            const auto* p = firstPduFromSink(sinkA);
            expect(p != nullptr);
            if (p) {
                expect(p->size() == 24UZ * sleipnir_detail::VOICE_FRAME_SIZE)
                    << "call 1 should NOT have sync frame";
            }
        }
    };

    "sync_pattern_present_in_sync_frame_bytes"_test = [] {
        SuperframeAssembler asm_{gr::property_map{
            {"name", std::string("asm_pat")},
            {"callsign", std::string("N0CALL")},
            {"enable_sync_frames", true},
            {"sync_frame_interval", 1}}};
        asm_.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(asm_.superframe_out.connect(sink).has_value());

        std::vector<std::uint8_t> opus(24UZ * 40UZ, 0x00U);
        asm_.handleOpusFramesPdu(makeOpusPdu(opus));

        const auto* pdu = firstPduFromSink(sink);
        expect(pdu != nullptr);
        if (pdu) {
            // First 8 bytes of the output are the sync frame header.
            std::span<const std::uint8_t> data(pdu->data(), pdu->size());
            expect(sleipnir_detail::isSyncFrame(data)) << "SYNC_PATTERN 0xDEADBEEFCAFEBABE not found";
        }
    };

    "callsign_bytes_present_in_voice_frame"_test = [] {
        SuperframeAssembler asm_{gr::property_map{
            {"name", std::string("asm_cs")},
            {"callsign", std::string("W1AW")},
            {"enable_sync_frames", false},
            {"sync_frame_interval", 1}}};
        asm_.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(asm_.superframe_out.connect(sink).has_value());

        std::vector<std::uint8_t> opus(24UZ * 40UZ, 0x00U);
        asm_.handleOpusFramesPdu(makeOpusPdu(opus));

        const auto* pdu = firstPduFromSink(sink);
        expect(pdu != nullptr);
        if (pdu) {
            // First voice frame starts at byte 0 (no sync prepended).
            std::span<const std::uint8_t> first_frame(pdu->data(), sleipnir_detail::VOICE_FRAME_SIZE);
            expect(sleipnir_detail::hasCallsignMarker(first_frame, "W1AW"))
                << "callsign bytes not found in first voice frame";
        }
    };

    "without_signing_no_auth_frame"_test = [] {
        // Without enable_signing, the first frame is a voice frame (type 0x00),
        // not a 64-byte auth frame.
        SuperframeAssembler asm_{gr::property_map{
            {"name", std::string("asm_nosign")},
            {"callsign", std::string("N0CALL")},
            {"enable_signing", false},
            {"enable_sync_frames", false},
            {"sync_frame_interval", 1}}};
        asm_.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(asm_.superframe_out.connect(sink).has_value());

        std::vector<std::uint8_t> opus(24UZ * 40UZ, 0x11U);
        asm_.handleOpusFramesPdu(makeOpusPdu(opus));

        const auto* pdu = firstPduFromSink(sink);
        expect(pdu != nullptr);
        if (pdu) {
            // Output should be exactly 24 voice frames (no extra auth frame).
            expect(pdu->size() == 24UZ * sleipnir_detail::VOICE_FRAME_SIZE)
                << "without signing, output should be 24 x 49 = 1176 bytes";
            // First byte of first frame should be FRAME_TYPE_VOICE (0x00), not auth.
            expect((*pdu)[0] == sleipnir_detail::FRAME_TYPE_VOICE)
                << "first frame must be a voice frame when signing is disabled";
        }
    };

    "enable_signing_false_same_output_regardless_of_key_path"_test = [] {
        auto makeAsm = [](const std::string& key_path) {
            SuperframeAssembler a{gr::property_map{
                {"name", std::string("asm_sign")},
                {"callsign", std::string("N0CALL")},
                {"enable_signing", false},
                {"private_key_path", key_path},
                {"enable_sync_frames", false},
                {"sync_frame_interval", 1}}};
            a.init(std::make_shared<gr::Sequence>());
            return a;
        };

        SuperframeAssembler a1 = makeAsm("");
        SuperframeAssembler a2 = makeAsm("/nonexistent/key.pem");

        gr::MsgPortIn sink1, sink2;
        expect(a1.superframe_out.connect(sink1).has_value());
        expect(a2.superframe_out.connect(sink2).has_value());

        std::vector<std::uint8_t> opus(24UZ * 40UZ, 0xBBU);
        a1.handleOpusFramesPdu(makeOpusPdu(opus));
        a2.handleOpusFramesPdu(makeOpusPdu(opus));

        const auto* p1 = firstPduFromSink(sink1);
        const auto* p2 = firstPduFromSink(sink2);
        expect(p1 != nullptr && p2 != nullptr);
        if (p1 && p2) {
            expect(p1->size() == p2->size())
                << "output size must be identical regardless of private_key_path when signing is off";
        }
    };
};

int main()
{
    return boost::ut::cfg<boost::ut::override>.run();
}
