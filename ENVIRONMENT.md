# Environment

The committed outputs (`outputs/`, `data/extracted/`) were produced, and are reproduced
byte for byte by `verification/check_all.py`, with:

- Python 3.14.0
- pdfplumber 0.11.8

The analysis uses the Python standard library only; pdfplumber is used for table
extraction only, and pytest for the tests. The manuscript states these versions, and
`verification/check_manuscript_numbers.py` reads them from this file.
