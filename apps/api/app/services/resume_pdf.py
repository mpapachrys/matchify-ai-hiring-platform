"""Render a resume draft to PDF with ReportLab.

Server-side rather than in the browser, for one reason: the generated PDF is
uploaded back to object storage as a real `resume` document and can be set as
the candidate's primary resume — so it is the same artifact that gets attached
to applications. A client-side download would produce a file the platform never
sees.

ReportLab over WeasyPrint/wkhtmltopdf because it is pure Python: no cairo,
pango, or headless browser in the image.
"""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.schemas.resume import ResumeDraft

INK = HexColor("#1a1a1a")
MUTED = HexColor("#585858")
RULE = HexColor("#d4d4d4")

#: One template today. Kept as a registry rather than inlined so adding a second
#: is a dict entry plus a label — no branching to reintroduce.
TEMPLATES: dict[str, dict] = {
    "professional": {
        "label": "Professional",
        "body_font": "Times-Roman",
        "bold_font": "Times-Bold",
        "heading_font": "Times-Bold",
        "accent": HexColor("#1a1a1a"),
        "name_size": 22,
        "align_header": TA_CENTER,
        "uppercase_headings": True,
        # Page geometry and type scale live in the spec too, so a future
        # template can be denser or airier without special-casing in render().
        "margin_x": 20 * mm,
        "margin_top": 18 * mm,
        "section_size": 11,
        "role_size": 10.5,
        "body_size": 10,
        "body_leading": 14,
        "section_space_before": 12,
    },
}

DEFAULT_TEMPLATE = "professional"


def _esc(value: str | None) -> str:
    """ReportLab paragraphs accept a mini-HTML dialect, so user text must be
    escaped or a stray `&` in a company name aborts the render."""
    return escape(value or "")


def _date_range(start: str | None, end: str | None, is_current: bool) -> str:
    left = (start or "").strip()
    right = "Present" if is_current else (end or "").strip()
    if left and right:
        return f"{left} — {right}"
    return left or right or ""


def _bullets(items: list[str], body_style: ParagraphStyle, spec: dict) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(_esc(i), body_style), leftIndent=14) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=14,
        # Match the body, or the glyph renders as a speck floating above the line.
        bulletFontName=spec["body_font"],
        bulletFontSize=body_style.fontSize,
        bulletOffsetY=-1,
    )


def render(draft: ResumeDraft, template: str = DEFAULT_TEMPLATE) -> bytes:
    spec = TEMPLATES.get(template, TEMPLATES[DEFAULT_TEMPLATE])

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=spec["margin_x"],
        rightMargin=spec["margin_x"],
        topMargin=spec["margin_top"],
        bottomMargin=14 * mm,
        title=f"{draft.full_name} — Resume",
        author=draft.full_name,
    )

    name_style = ParagraphStyle(
        "name",
        fontName=spec["heading_font"],
        fontSize=spec["name_size"],
        leading=spec["name_size"] + 4,
        textColor=spec["accent"],
        alignment=spec["align_header"],
        spaceAfter=2,
    )
    headline_style = ParagraphStyle(
        "headline",
        fontName=spec["body_font"],
        fontSize=11,
        leading=14,
        textColor=MUTED,
        alignment=spec["align_header"],
        spaceAfter=4,
    )
    contact_style = ParagraphStyle(
        "contact",
        fontName=spec["body_font"],
        fontSize=8.5,
        leading=12,
        textColor=MUTED,
        alignment=spec["align_header"],
    )
    section_style = ParagraphStyle(
        "section",
        fontName=spec["heading_font"],
        fontSize=spec["section_size"],
        leading=14,
        textColor=spec["accent"],
        spaceBefore=spec["section_space_before"],
        spaceAfter=3,
    )
    role_style = ParagraphStyle(
        "role",
        fontName=spec["bold_font"],
        fontSize=spec["role_size"],
        leading=13,
        textColor=INK,
    )
    meta_style = ParagraphStyle(
        "meta",
        fontName=spec["body_font"],
        fontSize=8.5,
        leading=12,
        textColor=MUTED,
        spaceAfter=2,
    )
    skills_style = ParagraphStyle(
        "skills",
        fontName=spec["body_font"],
        fontSize=spec["body_size"] - 0.5,
        leading=spec["body_leading"] - 1,
        textColor=MUTED,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "body",
        fontName=spec["body_font"],
        fontSize=spec["body_size"],
        leading=spec["body_leading"],
        textColor=INK,
        spaceAfter=4,
    )

    story: list = []

    # ── header ──
    story.append(Paragraph(_esc(draft.full_name) or "Your Name", name_style))
    if draft.headline:
        story.append(Paragraph(_esc(draft.headline), headline_style))

    contact_bits = [
        _esc(draft.email),
        _esc(draft.phone),
        _esc(", ".join(p for p in (draft.city, draft.country) if p)),
        _esc(draft.links.linkedin),
        _esc(draft.links.github),
        _esc(draft.links.portfolio),
    ]
    contact = "  ·  ".join(b for b in contact_bits if b)
    if contact:
        story.append(Paragraph(contact, contact_style))

    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=RULE, spaceAfter=2))

    def section(title: str) -> Paragraph:
        text = title.upper() if spec["uppercase_headings"] else title
        return Paragraph(_esc(text), section_style)

    # ── summary ──
    if draft.summary:
        story.append(section("Summary"))
        story.append(Paragraph(_esc(draft.summary), body_style))

    # ── experience ──
    if draft.experience:
        story.append(section("Experience"))
        for role in draft.experience:
            title_line = " — ".join(p for p in (_esc(role.title), _esc(role.company)) if p)
            meta_bits = [
                _date_range(role.start_date, role.end_date, role.is_current),
                _esc(role.location),
            ]
            block: list = [Paragraph(title_line or "Role", role_style)]
            meta = "  ·  ".join(b for b in meta_bits if b)
            if meta:
                block.append(Paragraph(meta, meta_style))
            if role.description:
                block.append(Paragraph(_esc(role.description), body_style))
            if role.skills:
                # Under the role rather than in one global list: a reader can see
                # what was used where, and how recently.
                block.append(
                    Paragraph(
                        f"<b>Skills:</b> {_esc('  ·  '.join(role.skills))}", skills_style
                    )
                )
            # Keeps a role's title from being orphaned at a page break.
            story.append(KeepTogether(block))

    # ── education ──
    if draft.education:
        story.append(section("Education"))
        for entry in draft.education:
            degree_line = " — ".join(
                p for p in (_esc(entry.degree), _esc(entry.institution)) if p
            )
            meta_bits = [
                _date_range(entry.start_date, entry.end_date, False),
                _esc(entry.field),
                _esc(entry.grade),
            ]
            block = [Paragraph(degree_line or "Qualification", role_style)]
            meta = "  ·  ".join(b for b in meta_bits if b)
            if meta:
                block.append(Paragraph(meta, meta_style))
            story.append(KeepTogether(block))

    # ── languages ──
    if draft.languages:
        story.append(section("Languages"))
        rendered = [
            f"{_esc(lang.name)}" + (f" ({_esc(lang.level)})" if lang.level else "")
            for lang in draft.languages
        ]
        story.append(Paragraph("  ·  ".join(rendered), body_style))

    # ── certifications ──
    if draft.certifications:
        story.append(section("Certifications"))
        for cert in draft.certifications:
            meta = "  ·  ".join(
                str(b) for b in (cert.issuer, cert.issued_year) if b
            )
            block = [Paragraph(_esc(cert.name), role_style)]
            if meta:
                block.append(Paragraph(_esc(meta), meta_style))
            story.append(KeepTogether(block))

    # ── achievements ──
    achievement_groups = [
        ("Career highlights", draft.achievements.career_highlights),
        ("Academic distinctions", draft.achievements.academic_distinctions),
        ("Awards & competitions", draft.achievements.awards_and_competitions),
        ("Projects & open source", draft.achievements.projects_and_open_source),
    ]
    if any(items for _, items in achievement_groups):
        story.append(section("Achievements"))
        for label, items in achievement_groups:
            if not items:
                continue
            story.append(Paragraph(f"<b>{_esc(label)}</b>", body_style))
            story.append(
                _bullets(items, body_style, spec)
            )


    document.build(story)
    return buffer.getvalue()
