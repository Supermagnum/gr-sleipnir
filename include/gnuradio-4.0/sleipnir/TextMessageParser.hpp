// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_SLEIPNIR_TEXTMESSAGEPARSER_HPP
#define GNURADIO4_SLEIPNIR_TEXTMESSAGEPARSER_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>
#include <gnuradio-4.0/annotated.hpp>
#include <gnuradio-4.0/sleipnir/detail/TextFrameFormat.hpp>

#include <array>
#include <cstdint>
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace gnuradio4::sleipnir {

GR_REGISTER_BLOCK(gnuradio4::sleipnir::TextMessageParser)

struct TextMessageParser : gr::Block<TextMessageParser> {
    using Description = gr::Doc<"Reassemble sleipnir TEXT frames into UTF-8 messages.">;

    gr::MsgPortIn  frame_in{};
    gr::MsgPortOut msg_out{};

    gr::Annotated<std::string, "local_callsign",           gr::Doc<"This station callsign">>            local_callsign          = std::string("N0CALL");
    gr::Annotated<bool,        "enable_verification",     gr::Doc<"Verify ECDSA signature">>          enable_verification     = false;
    gr::Annotated<std::string, "public_key_store_path",   gr::Doc<"CallsignKeyStore JSON path">>      public_key_store_path   = std::string("");
    gr::Annotated<bool,        "enable_decryption",       gr::Doc<"Decrypt ECIES payload">>           enable_decryption       = false;
    gr::Annotated<std::string, "private_key_path",        gr::Doc<"PEM private key for decrypt">>     private_key_path        = std::string("");
    gr::Annotated<std::string, "key_source",              gr::Doc<"gnupg|galdralag|json">>            key_source              = std::string("json");
    gr::Annotated<float,       "timeout_s",               gr::Doc<"Incomplete message timeout">>      timeout_s               = 30.0F;

    GR_MAKE_REFLECTABLE(TextMessageParser, frame_in, msg_out,
                        local_callsign, enable_verification, public_key_store_path,
                        enable_decryption, private_key_path, key_source, timeout_s);

    struct Pending {
        std::vector<std::optional<std::vector<std::uint8_t>>> frags;
        std::uint8_t                                            total{0U};
        std::uint64_t                                           last_ms{0U};
        std::array<std::uint8_t, detail::TEXT_CALLSIGN_BYTES>   dst{};
    };

    std::unordered_map<std::string, Pending>                _partials;
    std::unordered_set<std::string>                         _emitted;

    static void warn_crypto_stub_once() noexcept
    {
        static bool w = false;
        if (!w) {
            w = true;
            std::cerr << "TextMessageParser: verification/decryption require HAVE_GR_LINUX_CRYPTO (no-op).\n";
        }
    }

    void warn_requested_crypto() noexcept
    {
#ifndef HAVE_GR_LINUX_CRYPTO
        if (enable_verification || enable_decryption) {
            warn_crypto_stub_once();
        }
#endif
        (void)(enable_verification);
        (void)(enable_decryption);
        (void)(public_key_store_path);
        (void)(private_key_path);
        (void)(key_source);
    }

    std::string make_msg_key(std::span<const std::uint8_t> src_field, std::uint16_t msg_id) noexcept
    {
        std::string key(12UZ, '\0');
        std::memcpy(key.data(), src_field.data(), 10UZ);
        key[10U] = static_cast<char>(static_cast<std::uint8_t>((msg_id >> 8U) & 0xFFU));
        key[11U] = static_cast<char>(static_cast<std::uint8_t>(msg_id & 0xFFU));
        return key;
    }

    static bool completion_ready(const Pending& p) noexcept
    {
        if (p.total == 0U || p.frags.size() != static_cast<std::size_t>(p.total)) {
            return false;
        }
        for (const auto& f : p.frags) {
            if (!f.has_value()) {
                return false;
            }
        }
        return true;
    }

    void purge_timeout() noexcept
    {
        const std::uint64_t now = detail::steady_now_ms();
        const float         ts  = timeout_s;
        if (ts <= 0.0F) {
            return;
        }
        const std::uint64_t ttl_ms = static_cast<std::uint64_t>(ts * 1000.0F);
        for (auto it = _partials.begin(); it != _partials.end();) {
            if (!completion_ready(it->second) && (now - it->second.last_ms) > ttl_ms) {
                it = _partials.erase(it);
            } else {
                ++it;
            }
        }
    }

    bool destination_ok(std::span<const std::uint8_t> dst_field) noexcept
    {
        const auto lb = detail::encode_callsign_bytes(std::string_view(static_cast<std::string>(local_callsign)));
        if (detail::is_broadcast_callsign_field(dst_field)) {
            return true;
        }
        return std::equal(lb.begin(), lb.end(), dst_field.begin(), dst_field.end());
    }

    void publish_message(std::string   txt,
                          std::string   src_sv,
                          std::string   dst_sv,
                          std::uint16_t msg_id) noexcept
    {
        gr::property_map body;
        body[gr::convert_string_domain(std::string_view("text"))]
            = gr::pmt::Value(std::move(txt));
        body[gr::convert_string_domain(std::string_view("src"))]            = gr::pmt::Value(std::move(src_sv));
        body[gr::convert_string_domain(std::string_view("dst"))]             = gr::pmt::Value(std::move(dst_sv));
        body[gr::convert_string_domain(std::string_view("verified"))]         = gr::pmt::Value(false);
        body[gr::convert_string_domain(std::string_view("decrypted"))]        = gr::pmt::Value(false);
        body[gr::convert_string_domain(std::string_view("msg_id"))]          = gr::pmt::Value(static_cast<std::uint32_t>(msg_id));
        gr::Message msg;
        msg.cmd  = gr::message::Command::Notify;
        msg.data = std::move(body);
        auto w = msg_out.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        w[0]   = std::move(msg);
        w.publish(1UZ);
    }

    void finish_if_complete(const std::string& pkt_key, std::uint16_t msg_id_pub)
    {
        auto it = _partials.find(pkt_key);
        if (it == _partials.end()) {
            return;
        }
        Pending& pend = it->second;
        if (!completion_ready(pend)) {
            return;
        }
        if (_emitted.find(pkt_key) != _emitted.end()) {
            _partials.erase(it);
            return;
        }

        std::vector<std::uint8_t> src_raw(10UZ);
        std::memcpy(src_raw.data(), pkt_key.data(), 10UZ);
        const std::string src_sv = detail::decode_callsign_bytes(std::span<const std::uint8_t>(src_raw.data(), src_raw.size()));
        const std::string dst_sv = detail::decode_callsign_bytes(std::span<const std::uint8_t>(pend.dst.data(), pend.dst.size()));

        std::string utf8;
        for (const auto& slice : pend.frags) {
            utf8.append(slice->begin(), slice->end());
        }

        publish_message(std::move(utf8), std::move(src_sv), std::move(dst_sv), msg_id_pub);

        _emitted.insert(pkt_key);
        _partials.erase(it);
    }

    void handleFrame(std::span<const std::uint8_t> frame) noexcept
    {
        warn_requested_crypto();
        purge_timeout();

        std::uint8_t ftype                                    = 0U;
        std::array<std::uint8_t, detail::TEXT_CALLSIGN_BYTES> src{};
        std::array<std::uint8_t, detail::TEXT_CALLSIGN_BYTES> dst{};
        std::uint16_t                                          msg_id     = 0U;
        std::uint8_t                                           frag_idx   = 0U;
        std::uint8_t                                           frag_total = 0U;
        std::vector<std::uint8_t>                            payload;
        std::array<std::uint8_t, 8>                           mac{};
        mac.fill(0U);

        const bool ok =
            detail::parse_text_frame(frame, &ftype, std::span<std::uint8_t>(src.data(), src.size()),
                                    std::span<std::uint8_t>(dst.data(), dst.size()), &msg_id, &frag_idx, &frag_total, &payload, &mac);
        if (!ok || ftype != detail::FRAME_TYPE_TEXT) {
            return;
        }
        if (!destination_ok(std::span<const std::uint8_t>(dst.data(), dst.size()))) {
            return;
        }

        const std::string pkt_key = make_msg_key(std::span<const std::uint8_t>(src.data(), src.size()), msg_id);
        Pending&          slot = _partials[pkt_key];
        slot.last_ms = detail::steady_now_ms();

        if (slot.total == 0U) {
            slot.total = frag_total;
            slot.frags.assign(static_cast<std::size_t>(frag_total), std::nullopt);
            slot.dst   = dst;
        } else {
            // Enforce coherent metadata
            if (frag_total != slot.total || !std::equal(slot.dst.begin(), slot.dst.end(), dst.begin())) {
                return;
            }
        }

        if (frag_idx >= frag_total || frag_total != slot.total) {
            return;
        }

        slot.frags[static_cast<std::size_t>(frag_idx)] = std::move(payload);
        finish_if_complete(pkt_key, msg_id);
    }

    void handleInbound(gr::Message msg) noexcept
    {
        if (!msg.data.has_value()) {
            return;
        }
        const auto& body = msg.data.value();
        const auto  pk   = gr::convert_string_domain(std::string_view("pdu_bytes"));
        const auto  it   = body.find(pk);
        if (it == body.end()) {
            return;
        }
        const auto* t = it->second.get_if<gr::Tensor<std::uint8_t>>();
        if (!t || t->size() < detail::TEXT_FRAME_SIZE) {
            return;
        }
        handleFrame(std::span<const std::uint8_t>(t->data(), detail::TEXT_FRAME_SIZE));
    }

    void processMessages(gr::MsgPortIn& /* port */, gr::Message msg) noexcept
    {
        handleInbound(std::move(msg));
    }
};

} // namespace gnuradio4::sleipnir

#endif
