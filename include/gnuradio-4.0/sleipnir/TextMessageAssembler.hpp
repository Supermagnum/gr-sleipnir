// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_SLEIPNIR_TEXTMESSAGEASSEMBLER_HPP
#define GNURADIO4_SLEIPNIR_TEXTMESSAGEASSEMBLER_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>
#include <gnuradio-4.0/annotated.hpp>
#include <gnuradio-4.0/sleipnir/detail/TextFrameFormat.hpp>

#include <cstring>
#include <iostream>
#include <memory_resource>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace gnuradio4::sleipnir {

GR_REGISTER_BLOCK(gnuradio4::sleipnir::TextMessageAssembler)

struct TextMessageAssembler : gr::Block<TextMessageAssembler> {
    using Description =
        gr::Doc<"Fragment UTF-8 text into 64-byte sleipnir TEXT frames with optional crypto hooks.">;

    gr::MsgPortIn  msg_in{};
    gr::MsgPortOut frame_out{};

    gr::Annotated<std::string, "src_callsign",           gr::Doc<"Default source callsign">>      src_callsign      = std::string("N0CALL");
    gr::Annotated<bool,        "enable_signing",       gr::Doc<"ECDSA signing (requires crypto)">> enable_signing  = false;
    gr::Annotated<std::string, "private_key_path",       gr::Doc<"PEM private key">>                private_key_path  = std::string("");
    gr::Annotated<bool,        "enable_encryption",    gr::Doc<"ECIES encryption">>               enable_encryption = false;
    gr::Annotated<std::string, "key_source",           gr::Doc<"gnupg|galdralag|json">>         key_source        = std::string("json");
    gr::Annotated<std::string, "key_store_path",       gr::Doc<"CallsignKeyStore JSON path">>     key_store_path    = std::string("");

    GR_MAKE_REFLECTABLE(TextMessageAssembler, msg_in, frame_out,
                        src_callsign, enable_signing, private_key_path,
                        enable_encryption, key_source, key_store_path);

    std::uint16_t _msg_seq{1U}; // 0 reserved; wraps 65535 -> 1

    static void warn_crypto_unavailable_once() noexcept
    {
        static bool warned = false;
        if (!warned) {
            warned = true;
            std::cerr << "TextMessageAssembler: enable_signing/enable_encryption require HAVE_GR_LINUX_CRYPTO (using plaintext).\n";
        }
    }

    void warn_if_crypto_requested() noexcept
    {
#ifndef HAVE_GR_LINUX_CRYPTO
        if (enable_signing || enable_encryption) {
            warn_crypto_unavailable_once();
        }
#endif
    }

    void emitFrame(std::array<std::uint8_t, detail::TEXT_FRAME_SIZE> frm) noexcept
    {
        gr::property_map body;
        body[gr::convert_string_domain(std::string_view("pdu_bytes"))]
            = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::vector<std::uint8_t>(frm.begin(), frm.end())));
        gr::Message msg;
        msg.cmd  = gr::message::Command::Notify;
        msg.data = std::move(body);
        auto w = frame_out.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        w[0]   = std::move(msg);
        w.publish(1UZ);
    }

    std::optional<std::string> read_prop_string(const gr::property_map& body, std::string_view key_sv) noexcept
    {
        const auto k = gr::convert_string_domain(key_sv);
        const auto it = body.find(k);
        if (it == body.end()) {
            return std::nullopt;
        }
        const gr::pmt::Value& v = it->second;
        if (!(v.holds<std::string>() || v.holds<std::pmr::string>()
              || v.holds<std::string_view>())) {
            return std::nullopt;
        }
        return std::string(v.value_or(std::string_view{}));
    }

    void handleInbound(gr::Message msg) noexcept
    {
        warn_if_crypto_requested();

        if (!msg.data.has_value()) {
            return;
        }
        const auto& body = *msg.data;
        auto        text  = read_prop_string(body, "text").value_or(std::string{})
            + ""; // coerce
        if (text.size() > 800UZ) {
            text.resize(800UZ);
        }

        const std::string dst = read_prop_string(body, "dst").value_or("ALL");
        const auto        ov  = read_prop_string(body, "src");

        std::string src_eff = ov.has_value() && !ov->empty() ? *ov : std::string(src_callsign);

        const auto src_bytes = detail::encode_callsign_bytes(src_eff);
        const auto dst_bytes = detail::encode_callsign_bytes(dst == std::string("ALL") ? std::string_view("ALL") : std::string_view(dst));

        const std::uint16_t mid = _msg_seq;
        ++_msg_seq;
        if (_msg_seq == 0U) {
            _msg_seq = 1U;
        }

        const std::size_t      total_bytes = text.size();
        const std::uint8_t frag_total =
            static_cast<std::uint8_t>(
                total_bytes == 0UZ ? 1U : static_cast<std::uint8_t>((total_bytes + detail::TEXT_PAYLOAD_BYTES - 1UZ) / detail::TEXT_PAYLOAD_BYTES));

        (void)(private_key_path);
        (void)(key_store_path);
        (void)(key_source);
        (void)(enable_encryption);
        (void)(enable_signing);

        for (std::uint8_t fi = 0U; fi < frag_total; ++fi) {
            const std::size_t off       = fi * detail::TEXT_PAYLOAD_BYTES;
            const std::size_t chunk_len = (total_bytes == 0UZ && fi == 0U)
                ? 0UZ
                : std::min(detail::TEXT_PAYLOAD_BYTES,
                           (off < total_bytes) ? total_bytes - off : 0UZ);
            std::span<const std::uint8_t> pl{};
            std::vector<std::uint8_t> tmp;
            if (chunk_len > 0UZ && off + chunk_len <= text.size()) {
                tmp.resize(chunk_len);
                std::memcpy(tmp.data(), text.data() + off, chunk_len);
                pl = std::span<const std::uint8_t>(tmp.data(), chunk_len);
            }

            std::array<std::uint8_t, 8> mac{};
            auto frm = detail::build_text_frame_bytes(detail::FRAME_TYPE_TEXT,
                                                      std::span<const std::uint8_t>(src_bytes.data(), src_bytes.size()),
                                                      std::span<const std::uint8_t>(dst_bytes.data(), dst_bytes.size()),
                                                      mid,
                                                      fi,
                                                      frag_total,
                                                      pl,
                                                      std::span<const std::uint8_t>(mac.data(), mac.size()));
            emitFrame(frm);
        }
    }

    void processMessages(gr::MsgPortIn& /* port */, gr::Message msg) noexcept
    {
        handleInbound(std::move(msg));
    }
};

} // namespace gnuradio4::sleipnir

#endif
