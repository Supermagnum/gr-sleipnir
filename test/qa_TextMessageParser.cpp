// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>

#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>

#include <memory_resource>

#include <gnuradio-4.0/sleipnir/TextMessageAssembler.hpp>
#include <gnuradio-4.0/sleipnir/TextMessageParser.hpp>
#include <gnuradio-4.0/sleipnir/detail/TextFrameFormat.hpp>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using namespace boost::ut;
using namespace gnuradio4::sleipnir;
namespace dtl = gnuradio4::sleipnir::detail;

namespace {

struct RoutedText {
    std::string txt;
};

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

std::optional<RoutedText> pullOneText(gr::MsgPortIn& sink)
{
    if (sink.streamReader().available() < 1UZ) {
        return std::nullopt;
    }
    auto               span = sink.streamReader().template get<gr::SpanReleasePolicy::ProcessAll>(1UZ);
    const gr::Message& msg  = span[0UZ];
    if (!msg.data.has_value()) {
        return std::nullopt;
    }
    const auto& body = msg.data.value();
    const auto  kt   = gr::convert_string_domain(std::string_view("text"));
    const auto  it   = body.find(kt);
    if (it == body.end()) {
        return std::nullopt;
    }
    const gr::pmt::Value& v = it->second;
    if (!(v.holds<std::string>() || v.holds<std::pmr::string>() || v.holds<std::string_view>())) {
        return std::nullopt;
    }
    return RoutedText{std::string(v.value_or(std::string_view{}))};
}

std::size_t drainTextCount(gr::MsgPortIn& sink)
{
    std::size_t n = 0UZ;
    while (auto x = pullOneText(sink)) {
        ++n;
        static_cast<void>(x);
    }
    return n;
}

gr::Message makeAsmIn(std::string text, std::string dst, std::optional<std::string> src = std::nullopt)
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

std::vector<std::vector<std::uint8_t>> assembleToPdus(TextMessageAssembler& a, gr::MsgPortIn& a_sink,
                                                      gr::Message in)
{
    while (a_sink.streamReader().available() > 0UZ) {
        (void)a_sink.streamReader().template get<gr::SpanReleasePolicy::ProcessAll>(1UZ);
    }
    a.processMessages(a.msg_in, std::move(in));
    std::vector<std::vector<std::uint8_t>> out;
    while (a_sink.streamReader().available() > 0UZ) {
        auto        span = a_sink.streamReader().template get<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        const auto& msg  = span[0UZ];
        if (!msg.data.has_value()) {
            continue;
        }
        const auto&                          body = *msg.data;
        const auto                           key  = gr::convert_string_domain(std::string_view("pdu_bytes"));
        auto                                 it   = body.find(key);
        if (it != body.end()) {
            const auto* t = it->second.get_if<gr::Tensor<std::uint8_t>>();
            if (t && t->size() == dtl::TEXT_FRAME_SIZE) {
                out.emplace_back(t->begin(), t->end());
            }
        }
    }
    return out;
}

} // namespace

const suite<"TextMessageParser"> TextMessageParserSuite = [] {

    "single_fragment_round_trip"_test = [] {
        TextMessageAssembler a{gr::property_map{}};
        TextMessageParser    p{gr::property_map{{"local_callsign", std::string("KI4ABC")}}};
        a.init(std::make_shared<gr::Sequence>());
        p.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn a_sink, p_sink;
        expect(a.frame_out.connect(a_sink).has_value());
        expect(p.msg_out.connect(p_sink).has_value());

        const std::string orig = "hello parser";
        auto              fr   = assembleToPdus(a, a_sink, makeAsmIn(orig, "KI4ABC", std::string("N0CALL")));
        expect(eq(fr.size(), 1UZ));
        p.processMessages(p.frame_in, makePdu(std::move(fr[0])));
        const auto got = pullOneText(p_sink);
        expect(got.has_value());
        expect(eq(got->txt, orig));
    };

    "multi_fragment_in_order"_test = [] {
        TextMessageAssembler a{gr::property_map{}};
        TextMessageParser    p{gr::property_map{{"local_callsign", std::string("KI4ABC")}}};
        a.init(std::make_shared<gr::Sequence>());
        p.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn a_sink, p_sink;
        expect(a.frame_out.connect(a_sink).has_value());
        expect(p.msg_out.connect(p_sink).has_value());

        std::string long_;
        for (int i = 0; i < 80; ++i) {
            long_.push_back(static_cast<char>('0' + (i % 10)));
        }
        auto fr = assembleToPdus(a, a_sink, makeAsmIn(long_, "KI4ABC"));
        expect(fr.size() > 1UZ);
        for (auto& row : fr) {
            p.processMessages(p.frame_in, makePdu(std::move(row)));
        }
        const auto got = pullOneText(p_sink);
        expect(got.has_value());
        expect(eq(got->txt, long_));
    };

    "multi_fragment_out_of_order"_test = [] {
        TextMessageAssembler a{gr::property_map{}};
        TextMessageParser    p{gr::property_map{{"local_callsign", std::string("KI4ABC")}}};
        a.init(std::make_shared<gr::Sequence>());
        p.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn a_sink, p_sink;
        expect(a.frame_out.connect(a_sink).has_value());
        expect(p.msg_out.connect(p_sink).has_value());

        std::string long_;
        for (int i = 0; i < 80; ++i) {
            long_.push_back('z');
        }
        auto               fr_orig = assembleToPdus(a, a_sink, makeAsmIn(long_, "KI4ABC"));
        auto               fr      = fr_orig;
        std::reverse(fr.begin(), fr.end());
        for (auto& row : fr) {
            p.processMessages(p.frame_in, makePdu(std::move(row)));
        }
        const auto got = pullOneText(p_sink);
        expect(got.has_value());
        expect(eq(got->txt, long_));
    };

    "duplicate_msg_id_second_complete_silent"_test = [] {
        TextMessageAssembler a{gr::property_map{}};
        TextMessageParser    p{gr::property_map{{"local_callsign", std::string("KI4ABC")}}};
        a.init(std::make_shared<gr::Sequence>());
        p.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn a_sink, p_sink;
        expect(a.frame_out.connect(a_sink).has_value());
        expect(p.msg_out.connect(p_sink).has_value());

        auto fr_first = assembleToPdus(a, a_sink, makeAsmIn(std::string("same"), "KI4ABC"));
        for (auto& row : fr_first) {
            p.processMessages(p.frame_in, makePdu(row));
        }
        expect(eq(drainTextCount(p_sink), 1UZ));

        for (auto& row : fr_first) {
            p.processMessages(p.frame_in, makePdu(row));
        }
        expect(eq(drainTextCount(p_sink), 0UZ)) << "duplicate should not emit";
    };

    "incomplete_then_timeout_cleared"_test = [] {
        dtl::g_parser_now_ms_override.store(1'000'000ULL, std::memory_order_relaxed);
        TextMessageParser p{gr::property_map{{"local_callsign", std::string("KI4ABC")},
                                               {"timeout_s", 31.0F}}};
        p.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn p_sink;
        expect(p.msg_out.connect(p_sink).has_value());

        TextMessageAssembler a{gr::property_map{}};
        a.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn a_sink;
        expect(a.frame_out.connect(a_sink).has_value());

        std::vector<std::uint8_t> one;
        {
            auto fr =
                assembleToPdus(a, a_sink,
                               makeAsmIn(std::string(50, static_cast<char>('q')), std::string("KI4ABC")));
            expect(fr.size() >= 2UZ);
            one = std::move(fr.front());
        }

        p.processMessages(p.frame_in, makePdu(one));
        expect(eq(drainTextCount(p_sink), 0UZ));

        dtl::g_parser_now_ms_override.store(1'031'001ULL, std::memory_order_relaxed);
        TextMessageAssembler a2{gr::property_map{}};
        a2.init(std::make_shared<gr::Sequence>());
        expect(a2.frame_out.connect(a_sink).has_value());
        auto fr2 =
            assembleToPdus(a2, a_sink, makeAsmIn(std::string("after"), std::string("KI4ABC")));
        for (auto& row : fr2) {
            p.processMessages(p.frame_in, makePdu(std::move(row)));
        }

        const auto got = pullOneText(p_sink);
        expect(got.has_value());
        expect(eq(got->txt, std::string("after")));

        dtl::g_parser_now_ms_override.store(0ULL, std::memory_order_relaxed);
    };

    "broadcast_accepted_mismatched_local"_test = [] {
        TextMessageAssembler a{gr::property_map{}};
        TextMessageParser    p{gr::property_map{{"local_callsign", std::string("OTHER")}}};
        a.init(std::make_shared<gr::Sequence>());
        p.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn a_sink, p_sink;
        expect(a.frame_out.connect(a_sink).has_value());
        expect(p.msg_out.connect(p_sink).has_value());

        auto fr =
            assembleToPdus(a, a_sink,
                           makeAsmIn(std::string("bc"), std::string("ALL"), std::string("XM17")));
        for (auto& row : fr) {
            p.processMessages(p.frame_in, makePdu(std::move(row)));
        }
        const auto got = pullOneText(p_sink);
        expect(got.has_value());
        expect(eq(got->txt, std::string("bc")));
    };

    "assemble_then_parse_recover_exact"_test = [] {
        TextMessageAssembler a{gr::property_map{}};
        TextMessageParser    p{gr::property_map{{"local_callsign", std::string("AB1CD")}}};
        a.init(std::make_shared<gr::Sequence>());
        p.init(std::make_shared<gr::Sequence>());
        gr::MsgPortIn a_sink, p_sink;
        expect(a.frame_out.connect(a_sink).has_value());
        expect(p.msg_out.connect(p_sink).has_value());

        const std::string orig = "\xC4\x83UTF-8 test";
        auto              rows = assembleToPdus(a, a_sink,
                                     makeAsmIn(orig, std::string("AB1CD"), std::string("W9XYZ")));
        for (auto& row : rows) {
            p.processMessages(p.frame_in, makePdu(std::move(row)));
        }
        const auto got = pullOneText(p_sink);
        expect(got.has_value());
        expect(eq(got->txt, orig));
    };
};

int main()
{
    return boost::ut::cfg<boost::ut::override>.run();
}
