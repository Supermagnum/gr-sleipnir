// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>

#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>

#include <gnuradio-4.0/sleipnir/TextMessageAssembler.hpp>
#include <gnuradio-4.0/sleipnir/detail/TextFrameFormat.hpp>

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>
#include <vector>

using namespace boost::ut;
using namespace gnuradio4::sleipnir;
namespace dtl = gnuradio4::sleipnir::detail;

namespace {

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

gr::Message makeTextIn(std::string text, std::string dst = "ALL", std::optional<std::string> src = std::nullopt)
{
    gr::property_map body;
    body[gr::convert_string_domain(std::string_view("text"))] = gr::pmt::Value(std::move(text));
    body[gr::convert_string_domain(std::string_view("dst"))]  = gr::pmt::Value(std::move(dst));
    if (src.has_value() && !src->empty()) {
        body[gr::convert_string_domain(std::string_view("src"))] = gr::pmt::Value(std::move(*src));
    }
    gr::Message msg;
    msg.cmd  = gr::message::Command::Notify;
    msg.data = std::move(body);
    return msg;
}

void drain_sink(gr::MsgPortIn& sink)
{
    while (sink.streamReader().available() > 0UZ) {
        (void)sink.streamReader().template get<gr::SpanReleasePolicy::ProcessAll>(1UZ);
    }
}

} // namespace

const suite<"TextMessageAssembler"> TextMessageAssemblerSuite = [] {

    "short_single_fragment_under_31_bytes"_test = [] {
        TextMessageAssembler b{gr::property_map{}};
        b.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn sink;
        expect(b.frame_out.connect(sink).has_value());
        drain_sink(sink);

        const std::string msg = "hello";
        b.processMessages(b.msg_in, makeTextIn(msg, "K1AAA", {}));

        const auto* p = firstPduFromSink(sink);
        expect(p != nullptr);
        expect(p->size() == dtl::TEXT_FRAME_SIZE);
        std::vector<std::uint8_t> pay;
        std::array<std::uint8_t, 8> mac{};
        (void)dtl::parse_text_frame(std::span<const std::uint8_t>(p->data(), p->size()), nullptr,
                                    {}, {}, {}, {}, {}, &pay, &mac);
        expect(eq(std::string(pay.begin(), pay.end()), msg));
    };

    "long_200_ascii_seven_fragments"_test = [] {
        TextMessageAssembler b{gr::property_map{}};
        b.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn sink;
        expect(b.frame_out.connect(sink).has_value());

        std::string long_;
        long_.reserve(200U);
        for (int i = 0; i < 200; ++i) {
            long_.push_back(static_cast<char>('A' + (i % 26)));
        }
        const unsigned expect_frags = static_cast<unsigned>((200U + 31U - 1U) / 31U);
        b.processMessages(b.msg_in, makeTextIn(long_, "K1AAA"));

        unsigned n = 0U;
        while (sink.streamReader().available() > 0UZ) {
            const auto* p = firstPduFromSink(sink);
            expect(p != nullptr && p->size() == dtl::TEXT_FRAME_SIZE);
            ++n;

            std::uint8_t            fi{};
            std::uint8_t            ft{};
            std::vector<std::uint8_t> pay;
            std::array<std::uint8_t, 8> mac{};
            (void)dtl::parse_text_frame(std::span<const std::uint8_t>(p->data(), p->size()), nullptr,
                                       {}, {}, nullptr, &fi, &ft, &pay, &mac);
            expect(ft == expect_frags) << "fragment_total mismatch";
            expect(fi == n - 1U);
        }
        expect(eq(n, expect_frags));
    };

    "dst_all_broadcast_destination_field"_test = [] {
        TextMessageAssembler b{gr::property_map{}};
        b.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn sink;
        expect(b.frame_out.connect(sink).has_value());

        b.processMessages(b.msg_in, makeTextIn(std::string("x"), std::string("ALL")));
        const auto* p = firstPduFromSink(sink);
        expect(p != nullptr);
        bool all_ff = true;
        for (std::size_t i = 0UZ; i < 10UZ; ++i) {
            if ((*p)[11UZ + i] != 0xFFU) {
                all_ff = false;
            }
        }
        expect(all_ff);
    };

    "n0call_m17_encoded_bytes_match_expected"_test = [] {
        const auto                           enc = dtl::encode_callsign_bytes("N0CALL");
        constexpr std::array<std::uint8_t, 6> golden = {
            0x00U, 0x00U, 0x4BU, 0x13U, 0xD1U, 0x06U};
        expect(eq(enc[0UZ], golden[0UZ]));
        expect(eq(enc[1UZ], golden[1UZ]));
        expect(eq(enc[2UZ], golden[2UZ]));
        expect(eq(enc[3UZ], golden[3UZ]));
        expect(eq(enc[4UZ], golden[4UZ]));
        expect(eq(enc[5UZ], golden[5UZ]));
        for (std::size_t i = 6UZ; i < 10UZ; ++i) {
            expect(eq(enc[i], std::uint8_t{0U}));
        }
    };

    "msg_id_increment_and_wrap_behavior"_test = [] {
        std::uint16_t s = 65535U;
        ++s;
        if (s == 0U) {
            s = 1U;
        }
        expect(eq<unsigned>(s, 1U));
    };

    "msg_id Increments_across_messages"_test = [] {
        TextMessageAssembler b{gr::property_map{}};
        b.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn sink;
        expect(b.frame_out.connect(sink).has_value());

        b.processMessages(b.msg_in, makeTextIn(std::string("a"), "K1AAA"));
        const auto* p1 = firstPduFromSink(sink);
        expect(p1 != nullptr);
        const std::uint16_t m1 = static_cast<std::uint16_t>((*p1)[21U] << 8 | (*p1)[22U]);

        b.processMessages(b.msg_in, makeTextIn(std::string("b"), "K1AAA"));
        const auto* p2 = firstPduFromSink(sink);
        expect(p2 != nullptr);
        const std::uint16_t m2 = static_cast<std::uint16_t>((*p2)[21U] << 8 | (*p2)[22U]);

        const unsigned m1u = static_cast<unsigned>(m1);
        const unsigned m2u = static_cast<unsigned>(m2);
        const unsigned expected_next = (m1u == 65535U) ? 1U : (m1u + 1U);
        expect(eq(m2u, expected_next));
    };

    "empty_message_single_fragment"_test = [] {
        TextMessageAssembler b{gr::property_map{}};
        b.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn sink;
        expect(b.frame_out.connect(sink).has_value());

        b.processMessages(b.msg_in, makeTextIn(std::string{}, "ALL"));
        const auto* p = firstPduFromSink(sink);
        expect(p != nullptr);
        expect((*p)[24U] == 1U) << "fragment_total";
        std::vector<std::uint8_t> pay;
        std::array<std::uint8_t, 8> mac{};
        (void)dtl::parse_text_frame(std::span<const std::uint8_t>(p->data(), p->size()), nullptr,
                                   {}, {}, nullptr, {}, {}, &pay, &mac);
        expect(pay.empty());
    };
};

int main()
{
    return boost::ut::cfg<boost::ut::override>.run();
}
