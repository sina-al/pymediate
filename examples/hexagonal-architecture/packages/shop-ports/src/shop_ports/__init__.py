"""The ports: every interface the application needs the outside world to provide.

These are `typing.Protocol`s, so implementing one requires no import of this package —
an adapter just has to have the right methods. The dependency arrow points the way the
architecture wants it: adapters depend on these interfaces; these interfaces depend
only on the domain's entities.
"""
