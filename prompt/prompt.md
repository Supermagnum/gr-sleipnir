# Cursor Analysis Prompts for gr-sleipnir Test Results

This document contains ready-to-use prompts for Cursor to analyze Phase 2 test results and monitor Phase 3 progress.

## Table of Contents

- [Immediate Analysis (Phase 2 Data)](#immediate-analysis-phase-2-data)
- [Documentation Generation](#documentation-generation)
- [Real-Time Phase 3 Monitoring](#real-time-phase-3-monitoring)
- [Strategic Planning](#strategic-planning)
- [Fun/Interesting Analysis](#funinteresting-analysis)
- [Top 3 Recommendations](#top-3-recommendations)

---

## Immediate Analysis (Phase 2 Data)

### 1. Performance Visualization

```
Generate FER vs SNR plots from Phase 2 results showing:
- 4FSK performance curve
- Separate curves for clean and AWGN channels
- Mark the waterfall point (where FER crosses 1%)
- Add confidence intervals if data supports it
```

**Purpose:** Visual proof of 0 dB waterfall, clearly shows hard-decision FER floor

---

### 2. Detailed Statistics Tables

```
Create a detailed statistics table from Phase 2 showing:
- Pass rate by SNR range (-5 to 0, 0 to 5, 5 to 10, 10+)
- Mean/median/std FER for each SNR point
- Channel comparison (clean vs AWGN)
- Number of tests at each SNR level
```

**Purpose:** Quantitative performance breakdown for technical documentation

---

### 3. Audio Quality Analysis

```
Analyze WarpQ scores from Phase 2:
- WarpQ distribution by SNR
- Correlation between FER and WarpQ
- Identify SNR threshold where WarpQ consistently passes
- Show which tests failed on FER vs WarpQ
```

**Purpose:** Understand audio quality vs technical performance trade-offs

---

### 4. Waterfall Characterization

```
Find the exact waterfall SNR from Phase 2 data:
- Calculate SNR where FER = 1% (operational threshold)
- Show FER at key SNR points: -5, 0, +5, +10, +15, +20 dB
- Plot the waterfall 'knee' region
- Compare to theoretical LDPC performance
```

**Purpose:** Precise waterfall determination for competitive analysis

---

### 5. Sample Audio Files

```
Identify and list the output WAV files from Phase 2 at these SNR levels:
- SNR -5 dB (high FER, marginal)
- SNR 0 dB (waterfall, ~4-5% FER)
- SNR +10 dB (good signal, FER floor)
- SNR +20 dB (strong signal, still FER floor)

So I can listen and judge audio quality subjectively
```

**Purpose:** Subjective evaluation - hear the 4-5% FER floor in practice

---

### 6. Hard-Decision FER Floor Analysis

```
Analyze the 4-5% FER floor from Phase 2:
- Show FER at SNR > 10 dB (should be constant 4-5%)
- Calculate mean FER for 'high SNR' tests
- Identify any tests that achieved FER < 2% at high SNR
- Explain the distribution of errors across high-SNR tests
```

**Purpose:** Quantify hard-decision decoder limitation

---

### 7. Channel Model Validation

```
Verify channel models are working correctly from Phase 2:
- Compare clean vs AWGN FER at same SNR
- Show that FER decreases with increasing SNR
- Calculate the SNR 'gain' of clean over AWGN
- Identify any anomalies in the data
```

**Purpose:** Ensure test infrastructure validity

---

### 8. Test Coverage Report

```
Generate a test coverage report showing:
- Which SNR points were tested (and how many times)
- Distribution of tests across channels
- Any gaps in the test matrix
- Recommendations for Phase 3 focus areas
```

**Purpose:** Validate test completeness and identify any missing scenarios

---

### 9. Comparative Analysis Prep

```
Prepare comparison data for M17:
- gr-sleipnir 4FSK waterfall: ___ dB
- gr-sleipnir operational SNR (FER < 5%): ___ dB
- gr-sleipnir FER floor: ___ %
- Format ready to compare against M17's specs (+5 dB waterfall)
```

**Purpose:** Direct competitive comparison formatting

---

### 10. Failure Mode Analysis

```
Analyze test failures from Phase 2:
- What percentage failed on FER vs WarpQ?
- At what SNR do most failures occur?
- Are there any unexpected failure patterns?
- Show distribution of failure reasons
```

**Purpose:** Understand where and why tests fail

---

## Documentation Generation

### 11. Quick Start Performance Summary

```
Write a 1-page performance summary for Phase 2 including:
- Key finding: waterfall SNR
- FER floor limitation
- Comparison to M17 baseline
- Operational recommendations
- Format as markdown for GitHub README
```

**Purpose:** Concise summary for README/documentation

---

### 12. Technical Deep Dive

```
Generate detailed technical analysis:
- LDPC code performance (measured vs theoretical)
- Modulation/demodulation efficiency
- Frame synchronization behavior
- Error correction effectiveness
- Hard-decision decoder limitations
```

**Purpose:** In-depth technical documentation for paper/thesis

---

### 13. Publication-Ready Figures

```
Create publication-quality plots:
- FER vs SNR (log scale) with error bars
- Waterfall comparison (gr-sleipnir vs M17 vs FreeDV)
- Channel comparison (clean/AWGN)
- Use proper labels, legends, grid
- Export as PDF/PNG for paper
```

**Purpose:** Camera-ready figures for academic publication

---

## Real-Time Phase 3 Monitoring

### 14. Progress Dashboard

```
Create a real-time progress monitor showing:
- Current batch number
- Tests completed / remaining
- Estimated time to completion
- Current pass rate trend
- Any errors or warnings
```

**Purpose:** Track Phase 3 progress and catch issues early

---

### 15. Intermediate Results

```
Analyze any completed Phase 3 batches:
- Show early 8FSK results (if available)
- Compare to Phase 2 4FSK baseline
- Flag any unexpected behavior
- Update waterfall estimates
```

**Purpose:** Early insights from Phase 3 before full completion

---

## Strategic Planning

### 16. Next Steps Roadmap

```
Based on Phase 2 results, create a roadmap showing:
- What Phase 3 will prove/disprove
- Key decision points (8FSK vs 4FSK, crypto on/off)
- Areas needing further investigation
- On-air testing priorities
- Potential optimizations (soft-decision LDPC?)
```

**Purpose:** Strategic planning for project continuation

---

### 17. Deployment Scenarios

```
Create deployment scenario cards:
- Scenario: Portable/QRP operations
  - Recommended: 4FSK, no crypto, SNR ≥ 0 dB
  - Expected range: X km at Y watts
  
- Scenario: Base station
  - Recommended: 8FSK, with crypto, SNR ≥ 3 dB
  - Expected quality: near-toll

- Scenario: Mobile operations
  - Recommended: 4FSK, no crypto, SNR ≥ 5 dB
  - Expected: works with fading

- Scenario: Repeater/infrastructure
  - Recommended: 8FSK, sign only, SNR ≥ 5 dB
  - Expected: authenticated, quality audio

- Scenario: Emergency communications
  - Recommended: 4FSK, no crypto, SNR ≥ 0 dB
  - Expected: maximum range, simplicity
```

**Purpose:** User-focused deployment guidance

---

### 18. Hardware Requirements Document

```
Draft hardware requirements based on Phase 2:
- Minimum SNR: 0 dB (4FSK)
- Bandwidth: 9 kHz
- Frequency stability: TBD from Phase 3
- Processing requirements: CPU/memory for LDPC
- Radio compatibility: which models could work?
```

**Purpose:** Hardware integration planning

---

## Fun/Interesting Analysis

### 19. Power/Range Calculator

```
Create a calculator based on Phase 2 waterfall:
- gr-sleipnir at 0 dB vs M17 at +5 dB
- Show power savings: 5 dB = 3.16× less power
- Show range gain: 5 dB = ~1.78× more distance
- Create comparison table for 1W, 5W, 25W, 50W
```

**Purpose:** Practical real-world impact demonstration

**Example Output:**
| Power (gr-sleipnir) | Equivalent M17 Power | Range Multiplier |
|---------------------|----------------------|------------------|
| 1W                  | 3.16W               | 1.78×            |
| 5W                  | 15.8W               | 1.78×            |
| 25W                 | 79W                 | 1.78×            |
| 50W                 | 158W                | 1.78×            |

---

### 20. "What If" Scenarios

```
Model 'what if' scenarios:
- What if we achieve soft-decision LDPC? (FER floor → 0%)
- What if 8FSK waterfall is +6 dB instead of +3 dB?
- What if crypto overhead is 2 dB instead of 0.5 dB?
- How does each affect competitive position?
```

**Purpose:** Scenario planning and prioritization

---

## Top 3 Recommendations

### Most Useful Right Now

#### #1: Performance Visualization (Quick Win)

```
Generate FER vs SNR plot from Phase 2 with waterfall marked
```

**Why:** Visual proof of 0 dB waterfall, shows hard-decision floor clearly

**Expected Output:**
- Plot showing FER decreasing with SNR
- Clear waterfall around 0 dB
- Flat FER floor at 4-5% for SNR > 10 dB
- Comparison to M17 waterfall at +5 dB

---

#### #2: Audio Sample Identification (Subjective Test)

```
List output WAV files at SNR -5, 0, +10, +20 dB for listening test
```

**Why:** Hear the 4-5% FER floor, judge if it's acceptable

**Expected Output:**
- File paths to specific test outputs
- SNR and FER for each file
- Recommendation: listen to evaluate subjective quality
- Compare high-SNR (FER floor) vs low-SNR (marginal)

---

#### #3: Comparison Summary (Marketing)

```
Write 1-page summary: gr-sleipnir vs M17 performance comparison
```

**Why:** Clear competitive position, ready to share with community

**Expected Output:**
- Waterfall SNR comparison (0 dB vs +5 dB)
- Audio quality comparison (Opus vs Codec2)
- Power/range advantage calculation
- Bandwidth comparison (9 kHz both)
- Trade-offs (FER floor vs perfect decode)
- Recommended use cases

---

## Usage Instructions

1. **Copy any prompt above** (the text in code blocks)
2. **Paste into Cursor** as a direct question
3. **Cursor will analyze Phase 2 data** and generate the requested output
4. **Review and iterate** - ask follow-up questions to refine

## Notes

- All prompts assume Phase 2 results are available in `phase2_results.json`
- Prompts #14-15 can monitor Phase 3 in real-time
- Most prompts will work immediately, some depend on Phase 3 completion
- Adjust file paths and parameters as needed for your specific setup

## Expected Phase 3 Completion

- **Started:** 14:47
- **Duration:** ~10.7 hours
- **Estimated completion:** ~01:27 tomorrow morning
- **Total tests:** 1,288 tests across 26 batches

## What Phase 3 Will Add

- 8FSK performance data (waterfall comparison to 4FSK)
- Crypto overhead measurements (SIGN/ENCRYPT/BOTH)
- Fading channel performance (Rayleigh/Rician)
- Frequency offset tolerance (±100Hz, ±500Hz, ±1kHz)
- Complete operational envelope characterization

---

**Good luck with the analysis!** 🎯



Phase 3 (Edge Cases):
8. Boundary conditions
9. Key rotation
10. Sync loss/recovery
11. Mixed mode stress tests
