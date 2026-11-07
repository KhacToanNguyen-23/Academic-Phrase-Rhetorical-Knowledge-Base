"""Small self-authored text PDFs; no external corpus or rendering dependency."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_pdf(
    pages: tuple[str, ...] = (
        "Introduction\nDOI: 10.1234/pdf-paper\n"
        "This paper examines how retrieval methods support academic writing.\n"
        "The study evaluates several systems using controlled experiments.",
        "Results\nThe results suggest that retrieval improves the measured outcomes.\n"
        "Further studies are needed to understand the observed differences.",
    ),
    *,
    title: str = "A self-authored PDF paper",
    author: str = "Test Author",
    encrypted: bool = False,
) -> bytes:
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        commands = ["BT /F1 11 Tf 50 740 Td"]
        for line in text.splitlines():
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj 0 -16 Td")
        commands.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata({"/Title": title, "/Author": author, "/CreationDate": "D:20200101000000Z"})
    if encrypted:
        writer.encrypt("test-password")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_scanned_pdf() -> bytes:
    """One image-only page, without relying on Pillow/reportlab at test time."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    image = DecodedStreamObject()
    image.set_data(b"\xff")
    for name, value in {
        "/Type": NameObject("/XObject"),
        "/Subtype": NameObject("/Image"),
        "/ColorSpace": NameObject("/DeviceGray"),
    }.items():
        image[NameObject(name)] = value
    from pypdf.generic import NumberObject

    for name, value in {"/Width": 1, "/Height": 1, "/BitsPerComponent": 8}.items():
        image[NameObject(name)] = NumberObject(value)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im1"): writer._add_object(image)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"q 200 0 0 200 50 500 cm /Im1 Do Q")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
