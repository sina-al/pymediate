# Shop WeasyPrint adapter

`shop-adapter-weasyprint` turns invoice and monthly-statement data into compact, branded PDF
documents. It is separate from storage: rendering creates bytes, while another adapter decides
whether those bytes go to memory, S3, or Azure Blob Storage.

The package depends on `shop-ports` and WeasyPrint. It does not import the application, persistence,
bindings, or a cloud SDK.

## Module

### `shop.adapters.weasyprint.renderer`

`WeasyPrintDocumentRenderer` implements the invoice and statement renderer protocols. It builds
self-contained HTML and print CSS, then runs WeasyPrint in a worker thread so the synchronous
rendering engine does not block the application's asynchronous event loop.

The visual design uses system fonts and vector CSS decoration. It does not fetch remote styles,
images, or fonts. Normal one-page output is small, reproducible, and independent of network access.

The renderer receives only the presentation-safe data required by the use case. It does not load a
customer or order, choose a storage key, write an object, or send a document.

## Size and safety

The adapter caps every invoice and statement PDF below four megabytes. It checks the completed bytes
before returning them, so an unexpectedly large document fails before an object-storage write.

Keeping the renderer separate also prevents WeasyPrint and its native libraries from entering the
domain, ports, common adapters, or hosts that do not need PDF generation.

## Configuration and runtime dependencies

All three profiles select `WeasyPrintDocumentRenderer`. The cloud runtime images install the small
Pango and HarfBuzz libraries required by WeasyPrint; they do not install a browser. The example's
devcontainer includes the same native support.

On macOS, install the WeasyPrint native runtime once if it is not already available. Python
dependencies are managed by the example's uv workspace.

## Testing

Tests verify that invoice and statement output has a PDF signature and remains below 250 KB.
Application tests continue to depend only on the renderer protocols.

See the [complete Shop guide](../../README.md) for the invoice and statement journeys.
