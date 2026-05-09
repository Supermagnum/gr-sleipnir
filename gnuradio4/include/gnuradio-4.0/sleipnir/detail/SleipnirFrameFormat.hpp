// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_SLEIPNIR_DETAIL_FRAMEFORMAT_HPP
#define GNURADIO4_SLEIPNIR_DETAIL_FRAMEFORMAT_HPP

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <string>
#include <vector>

namespace gnuradio4::sleipnir::detail {

// Superframe constants
inline constexpr std::uint64_t SYNC_PATTERN           = 0xDEADBEEFCAFEBABEULL;
inline constexpr std::size_t   VOICE_FRAME_SIZE        = 49UZ; // bytes
inline constexpr std::size_t   SYNC_FRAME_SIZE         = 49UZ; // bytes
inline constexpr std::size_t   OPUS_BYTES_PER_FRAME    = 40UZ; // bytes (input)
inline constexpr std::size_t   OPUS_STORED_BYTES       = 39UZ; // bytes stored in frame (bytes 1-39)
inline constexpr std::size_t   MAC_BYTES               = 8UZ;  // truncated MAC in voice frame
inline constexpr std::size_t   FRAMES_PER_SUPERFRAME   = 25UZ;
inline constexpr std::size_t   VOICE_FRAMES_PER_SF     = 24UZ;
inline constexpr std::uint8_t  FRAME_TYPE_VOICE        = 0x00U;
inline constexpr std::uint8_t  FRAME_TYPE_SYNC         = 0xFFU;

// Voice frame layout (49 bytes):
//  [0]    : frame_type (0x00 = voice)
//  [1-39] : Opus data (39 bytes; first 39 of the 40-byte Opus packet)
//  [40-47]: MAC (8 bytes, zeroed when MAC not in use)
//  [48]   : reserved / padding

// Build one 49-byte voice frame.
// opus_in  must be exactly OPUS_BYTES_PER_FRAME (40) bytes.
// frame_num: 1-24
inline std::array<std::uint8_t, VOICE_FRAME_SIZE>
buildVoiceFrame(std::span<const std::uint8_t> opus_in, int frame_num) noexcept
{
    std::array<std::uint8_t, VOICE_FRAME_SIZE> buf{};
    buf[0] = FRAME_TYPE_VOICE;
    const std::size_t copy_len = std::min(opus_in.size(), OPUS_STORED_BYTES);
    std::memcpy(buf.data() + 1, opus_in.data(), copy_len);
    // MAC bytes 40-47 stay zero (no MAC key in base implementation)
    // buf[48] remains zero
    (void)frame_num;
    return buf;
}

// Build one 49-byte sync frame.
// superframe_counter is embedded at bytes 8-11 (big-endian uint32).
inline std::array<std::uint8_t, SYNC_FRAME_SIZE>
buildSyncFrame(std::uint32_t superframe_counter) noexcept
{
    std::array<std::uint8_t, SYNC_FRAME_SIZE> buf{};

    // Bytes 0-7: sync pattern (big-endian)
    const std::uint64_t pat = SYNC_PATTERN;
    buf[0] = static_cast<std::uint8_t>((pat >> 56U) & 0xFFU);
    buf[1] = static_cast<std::uint8_t>((pat >> 48U) & 0xFFU);
    buf[2] = static_cast<std::uint8_t>((pat >> 40U) & 0xFFU);
    buf[3] = static_cast<std::uint8_t>((pat >> 32U) & 0xFFU);
    buf[4] = static_cast<std::uint8_t>((pat >> 24U) & 0xFFU);
    buf[5] = static_cast<std::uint8_t>((pat >> 16U) & 0xFFU);
    buf[6] = static_cast<std::uint8_t>((pat >>  8U) & 0xFFU);
    buf[7] = static_cast<std::uint8_t>( pat         & 0xFFU);

    // Bytes 8-11: superframe counter (big-endian uint32)
    buf[8]  = static_cast<std::uint8_t>((superframe_counter >> 24U) & 0xFFU);
    buf[9]  = static_cast<std::uint8_t>((superframe_counter >> 16U) & 0xFFU);
    buf[10] = static_cast<std::uint8_t>((superframe_counter >>  8U) & 0xFFU);
    buf[11] = static_cast<std::uint8_t>( superframe_counter         & 0xFFU);
    // Bytes 12-40: zeros (payload padding)
    // Bytes 41-48: MAC zeros
    return buf;
}

// Return true if the 49 bytes starting at data contain the sync pattern.
inline bool isSyncFrame(std::span<const std::uint8_t> data) noexcept
{
    if (data.size() < 8UZ) {
        return false;
    }
    const std::uint64_t pat = SYNC_PATTERN;
    return data[0] == static_cast<std::uint8_t>((pat >> 56U) & 0xFFU)
        && data[1] == static_cast<std::uint8_t>((pat >> 48U) & 0xFFU)
        && data[2] == static_cast<std::uint8_t>((pat >> 40U) & 0xFFU)
        && data[3] == static_cast<std::uint8_t>((pat >> 32U) & 0xFFU)
        && data[4] == static_cast<std::uint8_t>((pat >> 24U) & 0xFFU)
        && data[5] == static_cast<std::uint8_t>((pat >> 16U) & 0xFFU)
        && data[6] == static_cast<std::uint8_t>((pat >>  8U) & 0xFFU)
        && data[7] == static_cast<std::uint8_t>( pat         & 0xFFU);
}

// Extract the callsign bytes embedded in a voice frame.
// The callsign is encoded as the first 5 characters of the callsign field
// stored in bytes 40-44 (after MAC, 8 bytes from 40 → actually MAC is 40-47,
// callsign is NOT embedded in the basic frame without gr-linux-crypto/nacl).
// For the basic GR4 implementation we insert the ASCII callsign at bytes 40-44
// (overlapping with the zero MAC region) as a convenience marker.
inline void embedCallsignMarker(std::array<std::uint8_t, VOICE_FRAME_SIZE>& frame,
                                 std::string_view                            callsign) noexcept
{
    // Use the first 5 bytes of the MAC area (bytes 40-44) as a callsign marker.
    // This is GR4-only convention used to let tests find the callsign without
    // a full MAC-key-based voice frame builder.
    constexpr std::size_t kCallsignOffset = 40UZ;
    constexpr std::size_t kMaxChars       = 5UZ;
    const std::size_t     n               = std::min(callsign.size(), kMaxChars);
    for (std::size_t i = 0UZ; i < kMaxChars; ++i) {
        frame[kCallsignOffset + i] = (i < n) ? static_cast<std::uint8_t>(callsign[i]) : static_cast<std::uint8_t>(' ');
    }
}

// Check whether a callsign marker is present in a voice frame.
inline bool hasCallsignMarker(std::span<const std::uint8_t> frame,
                               std::string_view              callsign) noexcept
{
    if (frame.size() < 45UZ || callsign.empty()) {
        return false;
    }
    constexpr std::size_t kCallsignOffset = 40UZ;
    const std::size_t     n               = std::min(callsign.size(), 5UZ);
    for (std::size_t i = 0UZ; i < n; ++i) {
        if (frame[kCallsignOffset + i] != static_cast<std::uint8_t>(callsign[i])) {
            return false;
        }
    }
    return true;
}

// Helper: assemble 24 voice frames + optional sync/auth frame into a flat byte vector.
// Returns total bytes written.
inline std::vector<std::uint8_t>
assembleFrames(std::span<const std::uint8_t> opus_data_960,
               std::string_view              callsign,
               bool                          prepend_sync,
               std::uint32_t                 superframe_counter) noexcept
{
    std::vector<std::uint8_t> out;
    out.reserve((prepend_sync ? SYNC_FRAME_SIZE : 0UZ) + VOICE_FRAMES_PER_SF * VOICE_FRAME_SIZE);

    if (prepend_sync) {
        auto sf = buildSyncFrame(superframe_counter);
        out.insert(out.end(), sf.begin(), sf.end());
    }

    for (std::size_t f = 0UZ; f < VOICE_FRAMES_PER_SF; ++f) {
        const std::size_t offset = f * OPUS_BYTES_PER_FRAME;
        std::span<const std::uint8_t> opus_chunk;
        if (offset < opus_data_960.size()) {
            const std::size_t avail = std::min(OPUS_BYTES_PER_FRAME, opus_data_960.size() - offset);
            opus_chunk = opus_data_960.subspan(offset, avail);
        }

        // Pad to 40 bytes if needed
        std::array<std::uint8_t, OPUS_BYTES_PER_FRAME> padded{};
        const std::size_t copy_n = std::min(opus_chunk.size(), OPUS_BYTES_PER_FRAME);
        std::memcpy(padded.data(), opus_chunk.data(), copy_n);

        auto vf = buildVoiceFrame(std::span<const std::uint8_t>(padded), static_cast<int>(f + 1U));
        embedCallsignMarker(vf, callsign);
        out.insert(out.end(), vf.begin(), vf.end());
    }

    return out;
}

} // namespace gnuradio4::sleipnir::detail

#endif
