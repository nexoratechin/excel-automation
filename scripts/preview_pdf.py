"""Render a PDF's pages to PNGs so they can be inspected.

    python scripts/preview_pdf.py docs/Client-Test-Guide.pdf build/preview
"""
import sys
from pathlib import Path

import pypdfium2 as pdfium

pdf_path = Path(sys.argv[1]).resolve()
out_dir = Path(sys.argv[2]).resolve()
out_dir.mkdir(parents=True, exist_ok=True)

doc = pdfium.PdfDocument(str(pdf_path))
print("pages:", len(doc))
for index in range(len(doc)):
    page = doc[index]
    bitmap = page.render(scale=1.6)
    image = bitmap.to_pil()
    target = out_dir / f"page-{index + 1}.png"
    image.save(target)
    print(f"  {target.name}  {image.width}x{image.height}")
