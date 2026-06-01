# PiStock — business services.
#
# Each module in this package groups the logic and REST endpoints of one
# domain (projects, boms, parts, stock, admin) + the cross-cutting
# helpers (codes, version generation). main.py assembles the routers and
# re-exports the public symbols for compatibility with the UI, the
# plugins and the tests (`main.Parts`, `main._flatten_bom`...).
