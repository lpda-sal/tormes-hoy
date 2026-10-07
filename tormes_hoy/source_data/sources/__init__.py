"""One isolated module per data source.

Each module exposes pure ``parse_*`` functions (tested with fixtures) and a
``fetch`` function that performs I/O through an injectable ``get_json``.
"""
