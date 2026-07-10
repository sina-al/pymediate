"""In-memory implementations of every port.

Two jobs, one package: these are the fakes the test suite constructs handlers with,
and they're also a legitimate deployment — the `memory` variant in compose runs the
real application on them. The other variants borrow this package's stub services
(payment gateway, mailer, storage, audit) and swap only the persistence.
"""
