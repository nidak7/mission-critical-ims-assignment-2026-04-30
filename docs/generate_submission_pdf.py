from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/nidak7/mission-critical-ims-assignment-2026-04-30"


def build_pdf(full_name: str) -> Path:
    file_name = f"{full_name} - Infrastructure ∕ SRE Intern Assignment.pdf"
    output_path = ROOT / file_name

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=8,
        )
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Infrastructure / SRE Intern Assignment",
        author=full_name,
    )

    story = [
        Paragraph("Infrastructure / SRE Intern Assignment", styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"Candidate: {full_name}", styles["Body"]),
        Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Body"]),
        Paragraph(f"GitHub: <link href='{REPO_URL}' color='blue'>{REPO_URL}</link>", styles["Body"]),
        Spacer(1, 8),
        Paragraph("Project Summary", styles["Section"]),
        Paragraph(
            "This submission is a runnable Incident Management System with async signal ingestion, incident workflow handling, RCA enforcement, and a web dashboard for active incidents.",
            styles["Body"],
        ),
        Paragraph("What Is Included", styles["Section"]),
        make_list(
            [
                "FastAPI backend with async ingestion and workflow APIs",
                "Dashboard for incident list, detail view, and RCA submission",
                "Sample data and reset script for demo flow",
                "Docker Compose file and local run instructions",
                "Tests for RCA validation, rate limiting, and service flow",
            ],
            styles["Body"],
        ),
        Paragraph("How To Run", styles["Section"]),
        make_list(
            [
                "python sample-data/reset_demo_state.py",
                "python backend/run_server.py",
                "Open http://localhost:8000",
                "python sample-data/send_scenario.py",
            ],
            styles["Body"],
        ),
        Paragraph("What Was Covered Beyond Core Functionality", styles["Section"]),
        make_list(
            [
                "Rate limiting on the ingestion API",
                "Bounded async queue for backpressure protection",
                "Retry logic around database writes",
                "Transactional state transitions",
                "Health endpoint and throughput logging",
                "Public GitHub repository with build scripts and config",
            ],
            styles["Body"],
        ),
        Paragraph("Verification", styles["Section"]),
        make_list(
            [
                "App startup verified locally",
                "Dashboard route verified",
                "Sample incidents loaded and reviewed in the UI",
                "Unit tests run for RCA validation, rate limiter, and service flow",
            ],
            styles["Body"],
        ),
    ]

    doc.build(story)
    return output_path


def make_list(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style)) for item in items],
        bulletType="bullet",
        leftIndent=16,
    )


def main() -> None:
    full_name = sys.argv[1].strip() if len(sys.argv) > 1 else "Full Name"
    build_pdf(full_name)
    print("Submission PDF generated.")


if __name__ == "__main__":
    main()
