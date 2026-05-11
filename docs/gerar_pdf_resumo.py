from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "resumo_sistema_ag_ouro.md"
OUTPUT = BASE_DIR / "resumo_sistema_ag_ouro.pdf"


def inline_markup(text: str) -> str:
    parts = text.split("`")
    rendered = []
    for index, part in enumerate(parts):
        safe = escape(part)
        if index % 2 == 1:
            rendered.append(f'<font name="Courier">{safe}</font>')
        else:
            rendered.append(safe)
    return "".join(rendered)


def build_story(markdown: str):
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#162027"),
        spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0f766e"),
        spaceBefore=14,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#28323b"),
        spaceAfter=7,
    )
    bullet = ParagraphStyle(
        "BulletCustom",
        parent=body,
        leftIndent=14,
        firstLineIndent=-8,
        spaceAfter=4,
    )

    story = []
    in_code_block = False
    code_lines = []

    def flush_code():
        if not code_lines:
            return
        text = "<br/>".join(escape(line) for line in code_lines)
        story.append(
            Paragraph(
                text,
                ParagraphStyle(
                    "CodeBlock",
                    parent=body,
                    fontName="Courier",
                    fontSize=8,
                    leading=11,
                    backColor=colors.HexColor("#eef3f7"),
                    borderColor=colors.HexColor("#d9e0e7"),
                    borderWidth=0.5,
                    borderPadding=6,
                    spaceBefore=4,
                    spaceAfter=8,
                ),
            )
        )
        code_lines.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if in_code_block:
                flush_code()
            in_code_block = not in_code_block
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 4))
            continue

        if stripped.startswith("# "):
            story.append(Paragraph(inline_markup(stripped[2:]), title))
            story.append(Paragraph("Guia introdutorio e registro do projeto", body))
            continue

        if stripped.startswith("## "):
            story.append(Paragraph(inline_markup(stripped[3:]), h2))
            continue

        if stripped.startswith("- "):
            story.append(Paragraph(inline_markup(stripped[2:]), bullet, bulletText="•"))
            continue

        story.append(Paragraph(inline_markup(stripped), body))

    flush_code()
    return story


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64717d"))
    canvas.drawString(2 * cm, 1.25 * cm, "Sistema AG Ouro - material de estudo")
    canvas.drawRightString(A4[0] - 2 * cm, 1.25 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera PDF simples a partir de Markdown.")
    parser.add_argument("--source", type=Path, default=SOURCE, help="Arquivo Markdown de entrada.")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Arquivo PDF de saida.")
    parser.add_argument("--title", default="Guia simples do sistema AG Ouro", help="Titulo interno do PDF.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source if args.source.is_absolute() else BASE_DIR / args.source
    output = args.output if args.output.is_absolute() else BASE_DIR / args.output
    markdown = source.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.8 * cm,
        title=args.title,
        author="Codex",
    )
    doc.build(build_story(markdown), onFirstPage=page_footer, onLaterPages=page_footer)
    print(output)


if __name__ == "__main__":
    main()
