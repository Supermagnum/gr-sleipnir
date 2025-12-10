# Contributing to gr-sleipnir

Thank you for your interest in contributing to gr-sleipnir! This document outlines the coding guidelines and contribution process.

## Coding Guidelines

gr-sleipnir follows the [GNU Radio coding guidelines](https://deepwiki.com/gnuradio/gnuradio/7-development-and-contributing#coding-guidelines).

### Python Coding Style

Python code should follow PEP8 with the following exceptions:

- **Max line length**: 120 characters
- **Ignored errors**: E265, E266, E275, E402, E501, E704, E712, E713, E714, E711, E721, E722, E741, W504, W605

These settings are configured in `.flake8` and `.editorconfig`.

#### Checking Code Style

Install flake8:
```bash
pip3 install flake8
```

Check code style:
```bash
flake8 python/
```

#### Auto-formatting

You can use `autopep8` to automatically fix many style issues:
```bash
pip3 install autopep8
autopep8 --in-place --max-line-length=120 python/*.py
```

### Git Commit Messages

Commit messages should follow this format:

- **Subject line**: Begin with component name followed by colon (e.g., `python:`, `grc:`, `docs:`)
- **Subject length**: Keep under 50 characters
- **Body**: Separate from subject with blank line, wrap at 72 characters
- **Content**: Explain what and why, not how

Examples:
```
python: Fix hierarchical block imports

The __init__.py was missing proper exports for hierarchical blocks,
preventing GRC from finding the blocks after installation.
```

```
grc: Add block definitions for TX/RX hierarchical blocks

Created .block.yml files for sleipnir_tx_hier and sleipnir_rx_hier
to enable GRC integration.
```

### Developer's Certificate of Origin (DCO)

All contributions must be signed using the DCO. Sign your commits with:
```bash
git commit -s -m "component: Your commit message"
```

The `-s` flag adds a "Signed-off-by" line to your commit message.

## Development Workflow

1. **Fork the repository** on GitHub
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following the coding guidelines
4. **Test your changes**:
   ```bash
   cd build
   make check_python
   ```
5. **Commit your changes** with proper DCO sign-off:
   ```bash
   git commit -s -m "component: Brief description"
   ```
6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Create a Pull Request** on GitHub

## Testing

Before submitting a PR, ensure all tests pass:

```bash
cd build
make check_python
```

Run the test suite:
```bash
cd tests
python3 -m pytest test_*.py -v
```

## Documentation

- Code should include docstrings for all classes and functions
- Use Google-style docstrings for consistency
- Update README.md if adding new features or changing behavior
- Add examples to `examples/` directory when adding new functionality

## Questions?

If you have questions about contributing, please open an issue on GitHub or contact the maintainers.

