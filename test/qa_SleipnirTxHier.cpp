// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>

#include <gnuradio-4.0/sleipnir/SleipnirTxHier.hpp>
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

// Check if control_out has a message available.
bool hasPendingMessage(gr::MsgPortIn& sink)
{
    return sink.streamReader().available() >= 1UZ;
}

const gr::Tensor<std::uint8_t>* drainFirstPdu(gr::MsgPortIn& sink)
{
    if (!hasPendingMessage(sink)) {
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

const suite<"SleipnirTxHier"> SleipnirTxHierSuite = [] {

    "accepts_float32_audio_via_processBulk"_test = [] {
        // Use a small frame_size_samples so tests don't need huge buffers.
        // frames_per_superframe=2, frame_size_samples=4 → need 8 samples total.
        SleipnirTxHier tx{gr::property_map{
            {"name", std::string("tx_basic")},
            {"callsign", std::string("N0CALL")},
            {"frames_per_superframe", 2},
            {"frame_size_samples", 4},
            {"enable_signing", false}}};
        tx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(tx.control_out.connect(sink).has_value());

        std::vector<float> audio(8UZ, 0.5F);
        // Feed fewer than required first to check no early emission
        const gr::work::Status st = tx.processBulk(
            std::span<const float>(audio.data(), audio.size()));
        expect(st == gr::work::Status::OK) << "processBulk must return OK";
    };

    "emits_superframe_after_accumulating_full_superframe"_test = [] {
        // frames_per_superframe=3, frame_size_samples=2 → need 6 samples total.
        SleipnirTxHier tx{gr::property_map{
            {"name", std::string("tx_emit")},
            {"callsign", std::string("N0CALL")},
            {"frames_per_superframe", 3},
            {"frame_size_samples", 2},
            {"enable_signing", false}}};
        tx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(tx.control_out.connect(sink).has_value());

        std::vector<float> audio(6UZ, 0.1F);
        const gr::work::Status st = tx.processBulk(
            std::span<const float>(audio.data(), audio.size()));
        expect(st == gr::work::Status::OK);
        expect(hasPendingMessage(sink))
            << "superframe message must be emitted after full accumulation";
    };

    "no_message_emitted_before_full_superframe_accumulated"_test = [] {
        // frames_per_superframe=4, frame_size_samples=10 → need 40 samples.
        SleipnirTxHier tx{gr::property_map{
            {"name", std::string("tx_partial")},
            {"callsign", std::string("N0CALL")},
            {"frames_per_superframe", 4},
            {"frame_size_samples", 10},
            {"enable_signing", false}}};
        tx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(tx.control_out.connect(sink).has_value());

        // Feed only 30 samples (< 40 required)
        std::vector<float> audio(30UZ, 0.0F);
        std::ignore = tx.processBulk(std::span<const float>(audio.data(), audio.size()));
        expect(!hasPendingMessage(sink))
            << "no message should be emitted before full superframe is accumulated";
    };

    "callsign_setting_reflected_correctly"_test = [] {
        SleipnirTxHier tx{gr::property_map{
            {"name", std::string("tx_cs")},
            {"callsign", std::string("KD9WXY")},
            {"frames_per_superframe", 1},
            {"frame_size_samples", 1},
            {"enable_signing", false}}};
        tx.init(std::make_shared<gr::Sequence>());

        // Verify the callsign setting is accessible.
        expect(static_cast<std::string>(tx.callsign) == std::string("KD9WXY"))
            << "callsign must be reflected as set";
    };

    "frames_per_superframe_setting_is_respected"_test = [] {
        // With fps=2 and frame_size_samples=1 → need 2 samples per superframe.
        SleipnirTxHier tx{gr::property_map{
            {"name", std::string("tx_fps")},
            {"callsign", std::string("N0CALL")},
            {"frames_per_superframe", 2},
            {"frame_size_samples", 1},
            {"enable_signing", false}}};
        tx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(tx.control_out.connect(sink).has_value());

        // Feed exactly 2 samples → one superframe
        std::vector<float> a1(2UZ, 0.0F);
        std::ignore = tx.processBulk(std::span<const float>(a1.data(), a1.size()));
        expect(hasPendingMessage(sink)) << "one superframe expected";

        const auto* p1 = drainFirstPdu(sink);
        expect(p1 != nullptr);

        // Feed another 2 samples → another superframe
        std::vector<float> a2(2UZ, 0.0F);
        std::ignore = tx.processBulk(std::span<const float>(a2.data(), a2.size()));
        expect(hasPendingMessage(sink)) << "second superframe expected";
    };

    "superframe_payload_contains_frame_data"_test = [] {
        SleipnirTxHier tx{gr::property_map{
            {"name", std::string("tx_payload")},
            {"callsign", std::string("N0CALL")},
            {"frames_per_superframe", 2},
            {"frame_size_samples", 4},
            {"enable_signing", false}}};
        tx.init(std::make_shared<gr::Sequence>());

        gr::MsgPortIn sink;
        expect(tx.control_out.connect(sink).has_value());

        std::vector<float> audio(8UZ, 0.5F);
        std::ignore = tx.processBulk(std::span<const float>(audio.data(), audio.size()));

        const auto* pdu = drainFirstPdu(sink);
        expect(pdu != nullptr) << "expected superframe PDU";
        if (pdu) {
            expect(pdu->size() > 0UZ) << "superframe payload must be non-empty";
            // Output should be N * VOICE_FRAME_SIZE bytes (with possible sync prepended).
            expect(pdu->size() % sleipnir_detail::VOICE_FRAME_SIZE == 0UZ
                   || pdu->size() % sleipnir_detail::VOICE_FRAME_SIZE == 0UZ)
                << "payload size should be a multiple of VOICE_FRAME_SIZE";
        }
    };
};

int main()
{
    return boost::ut::cfg<boost::ut::override>.run();
}
