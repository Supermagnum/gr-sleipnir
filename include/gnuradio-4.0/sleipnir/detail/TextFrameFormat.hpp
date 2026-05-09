// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_SLEIPNIR_DETAIL_TEXTFRAMEFORMAT_HPP
#define GNURADIO4_SLEIPNIR_DETAIL_TEXTFRAMEFORMAT_HPP

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include <atomic>
#include <chrono>

namespace gnuradio4::sleipnir::detail {

inline constexpr std::size_t TEXT_FRAME_SIZE           = 64UZ;
inline constexpr std::size_t TEXT_PAYLOAD_BYTES        = 31UZ;
inline constexpr std::size_t TEXT_CALLSIGN_BYTES       = 10UZ;
inline constexpr std::size_t TEXT_TRAILER_TAIL         = 6UZ; // MAGIC(4) + le16 len
inline constexpr std::uint8_t  FRAME_TYPE_TEXT         = 0x02U;

inline constexpr std::array<std::uint8_t, 4> TEXT_TRAILER_MAGIC = {
    0x54U, 0x45U, 0x58U, 0x54U}; // "TEXT"

inline std::atomic<std::uint64_t> g_parser_now_ms_override{0U}; // tests: nonzero = mocked time base

inline std::uint64_t steady_now_ms_fallback() noexcept
{
    using namespace std::chrono;
    return static_cast<std::uint64_t>(
        duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());
}

inline std::uint64_t steady_now_ms() noexcept
{
    const auto o = g_parser_now_ms_override.load(std::memory_order_relaxed);
    return (o != 0U) ? o : steady_now_ms_fallback();
}

inline int m17_charset_index(char c) noexcept
{
    // M17 alphabet: space + A-Z + 0-9 + '-' + '/'
    constexpr char kAlphabet[] = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/";
    for (std::size_t i = 0UZ; i < sizeof(kAlphabet) - 1UZ; ++i) {
        if (kAlphabet[i] == c) {
            return static_cast<int>(i);
        }
    }
    return 0;
}

inline char m17_charset_char(int idx) noexcept
{
    constexpr char kAlphabet[] = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/";
    if (idx < 0 || static_cast<std::size_t>(idx) >= sizeof(kAlphabet) - 1UZ) {
        return '?';
    }
    return kAlphabet[static_cast<std::size_t>(idx)];
}

// Pack callsign string (max 9 base-40 symbols) into 6 bytes followed by reserved 4 bytes (SSID / flags zero).
inline std::array<std::uint8_t, TEXT_CALLSIGN_BYTES> encode_callsign_bytes(std::string_view callsign) noexcept
{
    std::array<std::uint8_t, TEXT_CALLSIGN_BYTES> out{};
    out.fill(0U);

    // Broadcast / group ALL
    if (callsign.empty() || callsign == "ALL" || callsign == "BROADCAST") {
        out.fill(0xFFU);
        return out;
    }

    std::string norm;
    norm.reserve(9UZ);
    for (char ch : callsign) {
        if (norm.size() >= 9UZ) {
            break;
        }
        if (ch == '\0') {
            break;
        }
        norm.push_back(static_cast<char>((ch >= 'a' && ch <= 'z') ? (ch - 'a' + 'A') : ch));
    }

    norm.resize(std::max<std::size_t>(norm.size(), 9UZ), ' ');

    std::array<int, 9> vals{};
    for (std::size_t i = 0UZ; i < 9UZ; ++i) {
        vals[i] = m17_charset_index(norm[i]);
    }

    uint64_t acc = 0ULL;
    for (std::size_t i = 0UZ; i < 9UZ; ++i) {
        acc = acc * 40ULL + static_cast<std::uint64_t>(vals[8UZ - i]);
    }

    for (std::size_t i = 0UZ; i < 6UZ; ++i) {
        out[i] = static_cast<std::uint8_t>((acc >> (8UZ * (5UZ - i))) & 0xFFULL);
    }
    // Bytes 6-9 reserved zero
    return out;
}

inline bool is_broadcast_callsign_field(std::span<const std::uint8_t> field) noexcept
{
    if (field.size() < TEXT_CALLSIGN_BYTES) {
        return false;
    }
    bool all_ff = true;
    for (std::size_t i = 0UZ; i < TEXT_CALLSIGN_BYTES; ++i) {
        if (field[i] != 0xFFU) {
            all_ff = false;
            break;
        }
    }
    return all_ff;
}

inline std::string decode_callsign_bytes(std::span<const std::uint8_t> field) noexcept
{
    if (field.size() < TEXT_CALLSIGN_BYTES) {
        return {};
    }
    if (is_broadcast_callsign_field(field)) {
        return std::string("ALL");
    }

    uint64_t acc = 0ULL;
    for (std::size_t i = 0UZ; i < 6UZ; ++i) {
        acc = (acc << 8U) | static_cast<uint64_t>(field[i]);
    }

    std::array<int, 9> vals{};
    for (std::size_t i = 0UZ; i < 9UZ; ++i) {
        const int v = static_cast<int>(acc % 40ULL);
        vals[i]       = v;
        acc /= 40ULL;
    }

    std::string s;
    s.reserve(9UZ);
    for (std::size_t i = 0UZ; i < 9UZ; ++i) {
        s.push_back(m17_charset_char(vals[i]));
    }

    while (!s.empty() && s.back() == ' ') {
        s.pop_back();
    }
    return s;
}

inline std::array<std::uint8_t, TEXT_FRAME_SIZE>
build_text_frame_bytes(std::uint8_t                                              frame_type,
                       std::span<const std::uint8_t>                           src_encoded,
                       std::span<const std::uint8_t>                           dst_encoded,
                       std::uint16_t                                            msg_id,
                       std::uint8_t                                             frag_idx,
                       std::uint8_t                                             frag_total,
                       std::span<const std::uint8_t>                            payload_utf8,
                       std::span<const std::uint8_t>                            mac_tag) noexcept
{
    std::array<std::uint8_t, TEXT_FRAME_SIZE> out{};
    out[0] = frame_type;
    if (src_encoded.size() >= TEXT_CALLSIGN_BYTES) {
        std::memcpy(out.data() + 1U, src_encoded.data(), TEXT_CALLSIGN_BYTES);
    }
    if (dst_encoded.size() >= TEXT_CALLSIGN_BYTES) {
        std::memcpy(out.data() + 11U, dst_encoded.data(), TEXT_CALLSIGN_BYTES);
    }

    const std::uint8_t ml = static_cast<std::uint8_t>(msg_id & 0xFFU);
    const std::uint8_t mh = static_cast<std::uint8_t>((msg_id >> 8U) & 0xFFU);
    out[21U]                       = mh;
    out[22U]                       = ml;
    out[23U]                       = frag_idx;
    out[24U]                       = frag_total;
    const std::size_t plen       = std::min(payload_utf8.size(), TEXT_PAYLOAD_BYTES);
    if (plen > 0UZ) {
        std::memcpy(out.data() + 25U, payload_utf8.data(), plen);
    }
    const std::size_t mlen       = std::min(mac_tag.size(), 8UZ);
    if (mlen > 0UZ) {
        std::memcpy(out.data() + 56U, mac_tag.data(), mlen);
    }
    (void)frame_type;
    return out;
}

inline bool parse_text_frame(std::span<const std::uint8_t>                           frame,
                             std::uint8_t*                                           out_ftype,
                             std::span<std::uint8_t>                                 dst_src_encoded,
                             std::span<std::uint8_t>                                 dst_dst_encoded,
                             std::uint16_t*                                          out_msg_id,
                             std::uint8_t*                                           out_fi,
                             std::uint8_t*                                           out_ft,
                             std::vector<std::uint8_t>*                              out_payload,
                             std::array<std::uint8_t, 8>*                             out_mac) noexcept
{
    if (frame.size() < TEXT_FRAME_SIZE) {
        return false;
    }
    const std::uint8_t ft = frame[0];
    if (out_ftype != nullptr) {
        *out_ftype = ft;
    }
    if (dst_src_encoded.size() >= TEXT_CALLSIGN_BYTES) {
        std::memcpy(dst_src_encoded.data(), frame.data() + 1U, TEXT_CALLSIGN_BYTES);
    }
    if (dst_dst_encoded.size() >= TEXT_CALLSIGN_BYTES) {
        std::memcpy(dst_dst_encoded.data(), frame.data() + 11U, TEXT_CALLSIGN_BYTES);
    }
    if (out_msg_id != nullptr) {
        *out_msg_id = static_cast<std::uint16_t>((static_cast<std::uint16_t>(frame[21U]) << 8)
                                                 | static_cast<std::uint16_t>(frame[22U]));
    }
    if (out_fi != nullptr) {
        *out_fi = frame[23U];
    }
    if (out_ft != nullptr) {
        *out_ft = frame[24U];
    }
    if (out_payload != nullptr) {
        out_payload->assign(frame.begin() + 25U, frame.begin() + 25U + TEXT_PAYLOAD_BYTES);
        while (!out_payload->empty() && out_payload->back() == 0U) {
            out_payload->pop_back();
        }
    }
    if (out_mac != nullptr) {
        std::memcpy(out_mac->data(), frame.data() + 56U, 8UZ);
    }
    return ft == FRAME_TYPE_TEXT;
}

inline bool has_text_trailer(std::span<const std::uint8_t> pdu) noexcept
{
    return pdu.size() >= TEXT_TRAILER_TAIL && pdu[pdu.size() - 6UZ] == TEXT_TRAILER_MAGIC[0]
        && pdu[pdu.size() - 5UZ] == TEXT_TRAILER_MAGIC[1]
        && pdu[pdu.size() - 4UZ] == TEXT_TRAILER_MAGIC[2]
        && pdu[pdu.size() - 3UZ] == TEXT_TRAILER_MAGIC[3];
}

inline bool split_voice_and_text_trailer(std::span<const std::uint8_t>  pdu,
                                            std::span<const std::uint8_t>* voice_part,
                                            std::span<const std::uint8_t>* text_concat) noexcept
{
    const std::size_t n = pdu.size();
    if (!has_text_trailer(pdu)) {
        if (voice_part != nullptr) {
            *voice_part = pdu;
        }
        if (text_concat != nullptr) {
            *text_concat = std::span<const std::uint8_t>{};
        }
        return false;
    }
    const std::size_t tl = static_cast<std::size_t>(pdu[n - 2UZ]) | (static_cast<std::size_t>(pdu[n - 1UZ]) << 8UZ);
    if (tl % TEXT_FRAME_SIZE != 0UZ) {
        if (voice_part != nullptr) {
            *voice_part = pdu;
        }
        if (text_concat != nullptr) {
            *text_concat = std::span<const std::uint8_t>{};
        }
        return false;
    }
    if (TEXT_TRAILER_TAIL + tl > n) {
        if (voice_part != nullptr) {
            *voice_part = pdu;
        }
        if (text_concat != nullptr) {
            *text_concat = std::span<const std::uint8_t>{};
        }
        return false;
    }
    const std::size_t voice_len = n - TEXT_TRAILER_TAIL - tl;
    if (voice_part != nullptr) {
        *voice_part = pdu.first(voice_len);
    }
    if (text_concat != nullptr) {
        *text_concat = pdu.subspan(voice_len, tl);
    }
    return true;
}

inline std::vector<std::uint8_t>
append_text_trailer(std::vector<std::uint8_t>                                  voice_flat,
                     std::span<const std::uint8_t>                            text_concat) noexcept
{
    if (text_concat.empty()) {
        return voice_flat;
    }
    voice_flat.insert(voice_flat.end(), text_concat.begin(), text_concat.end());
    voice_flat.insert(voice_flat.end(), TEXT_TRAILER_MAGIC.begin(), TEXT_TRAILER_MAGIC.end());
    const std::uint16_t tl = static_cast<std::uint16_t>(text_concat.size());
    voice_flat.push_back(static_cast<std::uint8_t>(tl & 0xFFU));
    voice_flat.push_back(static_cast<std::uint8_t>((tl >> 8U) & 0xFFU));
    return voice_flat;
}

} // namespace gnuradio4::sleipnir::detail

#endif
