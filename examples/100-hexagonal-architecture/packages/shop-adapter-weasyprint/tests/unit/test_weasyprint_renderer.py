"""Verify the branded PDF adapter's output contract."""

from shop.adapters.weasyprint import WeasyPrintDocumentRenderer


async def test_statement_is_a_compact_pdf() -> None:
    # Arrange
    renderer = WeasyPrintDocumentRenderer()

    # Act
    document = await renderer.render_statement(7, 2026, 7, "EUR", 12, 123_456)

    # Assert
    assert document.startswith(b"%PDF-")
    assert len(document) < 250_000


async def test_invoice_is_a_compact_pdf() -> None:
    # Arrange
    renderer = WeasyPrintDocumentRenderer()

    # Act
    document = await renderer.render_invoice(42, 7, 1_500)

    # Assert
    assert document.startswith(b"%PDF-")
    assert len(document) < 250_000
