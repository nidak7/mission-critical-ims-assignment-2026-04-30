from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = ROOT / "docs"
REPO_URL = "https://github.com/nidak7/mission-critical-ims-assignment-2026-04-30"
DEFAULT_NAME = "Nida Farheen Khan"
DEFAULT_FILE_NAME = "Nida Farheen Khan - Infrastructure SRE Intern Assignment.pdf"


def build_pdf(full_name: str = DEFAULT_NAME) -> Path:
    DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = DOCS_ROOT / DEFAULT_FILE_NAME

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=7,
            textColor=colors.HexColor("#111827"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Mono",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=9,
            leading=12,
            backColor=colors.HexColor("#F3F4F6"),
            borderPadding=6,
            borderColor=colors.HexColor("#D1D5DB"),
            borderWidth=0.5,
            borderRadius=4,
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
        subject="Incident Management System assignment submission",
    )

    story = [
        Paragraph("Infrastructure / SRE Intern Assignment", styles["Title"]),
        Spacer(1, 10),
        Paragraph("Project: Incident Management System", styles["Body"]),
        Paragraph(f"Candidate: {full_name}", styles["Body"]),
        Paragraph(
            f"GitHub Link: <link href='{REPO_URL}' color='blue'>{REPO_URL}</link>",
            styles["Body"],
        ),
        Spacer(1, 12),
        Paragraph(
            "This PDF is the final submission artifact for the assignment and points to the public GitHub repository containing the full codebase, packaging, tests, and documentation.",
            styles["Body"],
        ),
        PageBreak(),
        Paragraph("Running Application Confirmation", styles["Section"]),
        Paragraph(
            "The application is runnable both locally and through Docker Compose. The repository includes the backend, frontend dashboard, sample data scripts, tests, configuration, and packaging files needed for evaluator review.",
            styles["Body"],
        ),
        Paragraph("Local run commands", styles["Body"]),
        code_block(
            [
                "python sample-data/reset_demo_state.py",
                "python backend/run_server.py",
                "python sample-data/send_scenario.py",
                "",
                "Open:",
                "http://localhost:8000",
            ],
            styles["Mono"],
        ),
        Paragraph("Docker command", styles["Body"]),
        code_block(["docker compose up --build"], styles["Mono"]),
        Paragraph("GitHub / Packaging Confirmation", styles["Section"]),
        Paragraph(
            "GitHub usage is mandatory for this assignment. The public repository contains the backend code, frontend/dashboard files, automated tests, sample data scripts, Docker Compose setup, README, configs/build scripts, and this final report PDF.",
            styles["Body"],
        ),
        bullet_list(
            [
                "Backend code",
                "Frontend/dashboard files",
                "Tests",
                "Sample data scripts",
                "Docker Compose",
                "README",
                "Configs/build scripts",
                "Final report PDF",
            ],
            styles["Body"],
        ),
        Paragraph("Project Overview", styles["Section"]),
        Paragraph(
            "The Incident Management System ingests operational signals, groups repeated signals from the same component, creates incidents, supports a workflow-driven incident lifecycle, requires RCA before closure, and calculates MTTR from RCA start and end time.",
            styles["Body"],
        ),
        Paragraph("Architecture", styles["Section"]),
        code_block(
            [
                "Signal API",
                "  -> Rate Limiter",
                "  -> Async Queue",
                "  -> Debounce Processor",
                "  -> Incident Service",
                "",
                "Incident / RCA -> SQLite",
                "Raw Signals    -> JSONL",
                "Dashboard      -> Backend APIs",
            ],
            styles["Mono"],
        ),
        Paragraph("Features Implemented", styles["Section"]),
        bullet_list(
            [
                "Async signal ingestion",
                "Bounded queue / backpressure handling",
                "Debouncing for repeated signals",
                "Raw signal storage in JSONL",
                "Incident dashboard",
                "Severity sorting",
                "Workflow: OPEN -> INVESTIGATING -> RESOLVED -> CLOSED",
                "Mandatory RCA before close",
                "MTTR calculation",
                "Health endpoint",
                "Throughput logging",
                "Rate limiting",
                "Retry logic for DB writes",
                "Automated tests",
            ],
            styles["Body"],
        ),
        Paragraph("Non-functional / Bonus Items", styles["Section"]),
        bullet_list(
            [
                "Rate limiting to protect the ingestion API",
                "Bounded async queue to avoid crashes during bursts",
                "Retry logic for database writes",
                "Backend workflow validation",
                "Frontend prevention of invalid transitions",
                "Health endpoint for observability",
                "Throughput metrics every 5 seconds",
                "Clean error handling",
                "Docker packaging",
                "Automated tests",
            ],
            styles["Body"],
        ),
        Paragraph("Testing Done", styles["Section"]),
        bullet_list(
            [
                "Health endpoint test",
                "Signal ingestion test",
                "Invalid payload test",
                "Debouncing test",
                "Raw signal linking test",
                "Valid workflow transition test",
                "Invalid transition test",
                "RCA validation test",
                "MTTR calculation test",
                "Rate limiting test",
                "Dashboard state test",
            ],
            styles["Body"],
        ),
        Paragraph("Test command", styles["Body"]),
        code_block(["python -m unittest discover -s backend/tests"], styles["Mono"]),
        Paragraph("Demo Flow", styles["Section"]),
        numbered_list(
            [
                "Start app",
                "Load sample data",
                "Open dashboard",
                "Select RDBMS_PRIMARY_01",
                "Mark Investigating",
                "Mark Resolved",
                "Fill and save RCA",
                "Close Incident",
                "Verify MTTR and status",
            ],
            styles["Body"],
        ),
        Paragraph("Known Limitations", styles["Section"]),
        bullet_list(
            [
                "SQLite is used for assignment simplicity.",
                "JSONL is used instead of a production NoSQL store.",
                "The dashboard is a local lightweight implementation.",
                "A production version could use Kafka, Redis, PostgreSQL, MongoDB, and Prometheus/Grafana.",
            ],
            styles["Body"],
        ),
        Paragraph("Conclusion", styles["Section"]),
        Paragraph(
            "This submission meets the assignment requirements with a runnable Incident Management System, documented setup, automated tests, packaging through GitHub and Docker Compose, and a single PDF artifact for evaluation.",
            styles["Body"],
        ),
    ]

    doc.build(story)
    return output_path


def bullet_list(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style)) for item in items],
        bulletType="bullet",
        leftIndent=16,
    )


def numbered_list(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style)) for item in items],
        bulletType="1",
        leftIndent=16,
    )


def code_block(lines: list[str], style: ParagraphStyle) -> Preformatted:
    return Preformatted("\n".join(lines), style)


def main() -> None:
    full_name = sys.argv[1].strip() if len(sys.argv) > 1 else DEFAULT_NAME
    output_path = build_pdf(full_name)
    print(output_path)


if __name__ == "__main__":
    main()
