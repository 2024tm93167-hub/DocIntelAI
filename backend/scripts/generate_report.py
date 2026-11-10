"""Generate the DocIntel AI final semester report as a .docx file.

The document is built on top of the BITS sample dissertation docx so that
styles, heading numbering, typography, page setup and footers match the
reference report exactly:

  Heading 1 (20pt bold)  -> chapter titles, auto-numbered "1."
  Heading 3 (16pt bold)  -> sections, auto-numbered "1.1"
  Heading 4 (14pt bold)  -> sub-sections, auto-numbered "1.1.1"
  Heading 5 (12pt bold)  -> bold label lines (e.g. "Abstract:")
  Body Text (12pt TNR)   -> normal paragraphs
  List Paragraph         -> bullets (numId 6) / numbered items (numId 5)

Front matter uses lower-roman page numbers; chapters restart at page 1
(arabic), matching the sample's two-section layout.

Run from the backend directory:
    venv/bin/python scripts/generate_report.py

Output: ../docs/DocIntel-Final-Report.docx
"""
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

REFERENCE = Path("/Users/satyasivasundarsalagrama/Downloads/2023tm93691_Final Dissertation Report.docx")
OUT = Path(__file__).resolve().parents[2] / "docs" / "DocIntel-Final-Report.docx"

doc = Document(str(REFERENCE))


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------
def style_by_id(sid):
    for s in doc.styles:
        if getattr(s, "style_id", None) == sid:
            return s
    raise KeyError(f"style {sid} not found")


S_H1 = style_by_id("Heading1")
S_H2 = style_by_id("Heading2")
S_H3 = style_by_id("Heading3")
S_H4 = style_by_id("Heading4")
S_H5 = style_by_id("Heading5")
S_BODY = style_by_id("BodyText")
S_LIST = style_by_id("ListParagraph")
S_TBLP = None
try:
    S_TBLP = style_by_id("TableParagraph")
except KeyError:
    pass

NUM_HEADINGS = 4   # numId 4 -> %1. / %1.%2 / %1.%2.%3
NUM_NUMBERED = 5   # numId 5 -> "1." numbered list items
NUM_BULLET = 6     # numId 6 -> "●" bullet items


def add_numpr(para, num_id, ilvl=0):
    pPr = para._p.get_or_add_pPr()
    numPr = OxmlElement("w:numPr")
    ilvl_el = OxmlElement("w:ilvl")
    ilvl_el.set(qn("w:val"), str(ilvl))
    numId_el = OxmlElement("w:numId")
    numId_el.set(qn("w:val"), str(num_id))
    numPr.append(ilvl_el)
    numPr.append(numId_el)
    pPr.append(numPr)


def para(text="", style=None, align=None, num_id=None, ilvl=0):
    p = doc.add_paragraph(style=style)
    if text:
        p.add_run(text)
    if align is not None:
        p.alignment = align
    if num_id is not None:
        add_numpr(p, num_id, ilvl)
    return p


def h1(text, numbered=True):
    """Chapter heading - Heading 1, numbered '1.' when numbered=True."""
    p = para(style=S_H1, align=WD_ALIGN_PARAGRAPH.LEFT)
    p.add_run(text)
    if numbered:
        add_numpr(p, NUM_HEADINGS, 0)
    return p


def h3(text, numbered=True):
    """Section heading - Heading 3, numbered '1.1'."""
    p = para(style=S_H3, align=WD_ALIGN_PARAGRAPH.LEFT)
    p.add_run(text)
    if numbered:
        add_numpr(p, NUM_HEADINGS, 1)
    return p


def h4(text, numbered=True):
    """Sub-section heading - Heading 4, numbered '1.1.1'."""
    p = para(style=S_H4, align=WD_ALIGN_PARAGRAPH.LEFT)
    p.add_run(text)
    if numbered:
        add_numpr(p, NUM_HEADINGS, 2)
    return p


def h5(text):
    """Bold label line - Heading 5 (12pt bold)."""
    p = para(style=S_H5)
    p.add_run(text)
    return p


def body(text, justify=True):
    p = para(style=S_BODY)
    p.add_run(text)
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def bullets(items, num_id=NUM_BULLET):
    for item in items:
        para(text=item, style=S_LIST, num_id=num_id, ilvl=0)


def numbered(items):
    bullets(items, num_id=NUM_NUMBERED)


def fig(text):
    """Figure caption - centred italic body text."""
    p = para(style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
    run = p.add_run(text)
    run.font.italic = True
    return p


def table(headers, rows):
    """Bordered grid table with bold header row."""
    t = doc.add_table(rows=1, cols=len(headers))
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        borders.append(el)
    tblPr.append(borders)
    for i, head in enumerate(headers):
        cell = t.rows[0].cells[i]
        cp = cell.paragraphs[0]
        run = cp.add_run(head)
        run.font.bold = True
        if S_TBLP is not None:
            cp.style = S_TBLP
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cp = cells[i].paragraphs[0]
            cp.add_run(val)
            if S_TBLP is not None:
                cp.style = S_TBLP
    doc.add_paragraph()


def bold_term_para(term, definition):
    p = para(style=S_BODY)
    run = p.add_run(f"{term}: ")
    run.font.bold = True
    p.add_run(definition)


def page_break_clean():
    p = doc.add_paragraph(style=S_BODY)
    r = p.add_run()
    brk = OxmlElement("w:br")
    brk.set(qn("w:type"), "page")
    r._r.append(brk)


# ------------------------------------------------------------------
# clear the reference document's content, keep final sectPr
# ------------------------------------------------------------------
body_el = doc.element.body
final_sectPr = None
for child in list(body_el):
    if child.tag == qn("w:sectPr"):
        final_sectPr = child
        continue
    body_el.remove(child)

# normalise final section: page size letter, 0.75" side margins
pgSz = final_sectPr.find(qn("w:pgSz"))
if pgSz is None:
    pgSz = OxmlElement("w:pgSz")
    final_sectPr.append(pgSz)
pgSz.set(qn("w:w"), "12240")
pgSz.set(qn("w:h"), "15840")
pgMar = final_sectPr.find(qn("w:pgMar"))
if pgMar is None:
    pgMar = OxmlElement("w:pgMar")
    final_sectPr.append(pgMar)
for attr, val in (("top", "1382"), ("right", "1080"), ("bottom", "284"),
                  ("left", "1080"), ("header", "720"), ("footer", "720")):
    pgMar.set(qn(f"w:{attr}"), str(val))

# strip inherited header/footer refs and page-number config
for tag in ("headerReference", "footerReference", "pgNumType", "titlePg"):
    for el in final_sectPr.findall(qn(f"w:{tag}")):
        final_sectPr.remove(el)


def new_section_break(fmt, start):
    """End the current section: append a paragraph whose pPr holds a sectPr."""
    p = doc.add_paragraph()
    sect = deepcopy(final_sectPr)
    pPr = p._p.get_or_add_pPr()
    pPr.append(sect)
    set_pgnum(sect, fmt, start)
    return sect


def set_pgnum(sect, fmt, start=None):
    for el in sect.findall(qn("w:pgNumType")):
        sect.remove(el)
    el = OxmlElement("w:pgNumType")
    el.set(qn("w:fmt"), fmt)
    if start is not None:
        el.set(qn("w:start"), str(start))
    sect.append(el)


def add_page_field(paragraph):
    """Insert a PAGE field into a paragraph."""
    for kind, extra in (("begin", None), (None, " PAGE \\* MERGEFORMAT "), ("end", None)):
        r = OxmlElement("w:r")
        if kind is not None:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), kind)
            r.append(fld)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = extra
            r.append(instr)
        paragraph._p.append(r)


# ==================================================================
# FRONT MATTER (lower-roman page numbers)
# ==================================================================

# ---- cover page ----
para("A REPORT ON", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para(style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER).add_run("DocIntel AI").font.size = Pt(16)
para("An AI-Assisted Document Editor with Version Control and Real-Time "
     "Collaboration", style=S_H1, align=WD_ALIGN_PARAGRAPH.CENTER)
para("BY", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("<STUDENT NAME>", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("<BITS ID>", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("AT", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("<EMPLOYING ORGANIZATION, LOCATION>", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("BIRLA INSTITUTE OF TECHNOLOGY & SCIENCE, PILANI", style=S_BODY,
     align=WD_ALIGN_PARAGRAPH.CENTER)
para("<Month Year>", style=S_H1, align=WD_ALIGN_PARAGRAPH.CENTER)
page_break_clean()

# ---- title page ----
para("A REPORT ON", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("DocIntel AI - An AI-Assisted Document Editor with Version Control "
     "and Real-Time Collaboration", style=S_H2, align=WD_ALIGN_PARAGRAPH.CENTER)
para("BY", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("<STUDENT NAME>  <BITS ID>", style=S_BODY, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Prepared in partial fulfillment of the WILP Dissertation Course "
     "Under the Supervision of <Supervisor Name>", style=S_H2,
     align=WD_ALIGN_PARAGRAPH.CENTER)
para("Supervisor: <Name>    Additional Examiner: <Name>", style=S_H2,
     align=WD_ALIGN_PARAGRAPH.CENTER)
para("Faculty Mentor: <Name>", style=S_H2, align=WD_ALIGN_PARAGRAPH.CENTER)
para("<Month Year>", style=S_H2, align=WD_ALIGN_PARAGRAPH.CENTER)
page_break_clean()

# ---- certificate ----
para("CERTIFICATE", style=S_H1, align=WD_ALIGN_PARAGRAPH.CENTER)
body("This is to certify that the Dissertation entitled DocIntel AI - An "
     "AI-Assisted Document Editor with Version Control and Real-Time "
     "Collaboration and submitted by <STUDENT NAME> (BITS ID <BITS ID>) in "
     "partial fulfillment of the requirements for the award of the degree "
     "of M.Tech. Software Engineering, is a record of bonafide work carried "
     "out under my supervision and guidance.")
body("")
h5("Signature of Student:                 Signature of Supervisor:")
h5("Date:                                 Date:")
page_break_clean()

# ---- acknowledgements ----
para("Acknowledgements", style=S_H1)
body("I would like to express my sincere gratitude to my supervisor for "
     "their guidance and support throughout the course of this project. "
     "I also thank the faculty and staff of BITS Pilani WILP division for "
     "providing the academic framework and resources that made this work "
     "possible.")
page_break_clean()

# ---- abstract ----
h5("Abstract:")
body("DocIntel AI is an AI-assisted document editing platform that combines "
     "a rich-text editor, LLM-powered writing assistance, structured version "
     "control, and real-time collaboration within a single system. The "
     "backend is implemented in FastAPI with a pluggable AI provider layer "
     "(OpenAI-compatible or local Ollama), Cloud Firestore for persistence, "
     "and Firebase Authentication for identity verification. The frontend is "
     "built in Angular with a TipTap/ProseMirror editor presented as a "
     "page-first word-processor workspace.")
body("Key contributions of the work include a preview-only AI workflow with "
     "eleven context-aware writing actions, a persistent suggestion system "
     "with revision-aware acceptance, optimistic concurrency control using "
     "Firestore transactions, automatic and manual version checkpoints with "
     "transactional restore, role-based access control for shared documents, "
     "WebSocket-based presence and remote cursors, and a metrics "
     "instrumentation framework that supports usability, productivity, and "
     "document-quality evaluation.")
body("The system was verified through 202 backend tests and 88 frontend "
     "tests. Evaluation instruments for SUS scoring, latency benchmarking, "
     "keystroke analysis, and readability/grammar comparison are implemented "
     "and ready for participant studies.")
body("Keywords: AI-assisted writing, document editor, version control, "
     "collaborative editing, LLM, FastAPI, Angular, Firestore.")
page_break_clean()

# ---- table of contents (static, matching the sample's manual TOC) ----
para("Table of contents", style=S_H1)
toc = [
    ("Cover", "i", 0), ("Title Page", "ii", 0), ("Acknowledgements", "iii", 0),
    ("Abstract Sheet", "iv", 0),
    ("Introduction", "1", 0),
    ("Project Objectives", "1", 1), ("Scope of the Work", "2", 1),
    ("Significance and Expected Outcome", "4", 1),
    ("Literature Review", "5", 0),
    ("AI-Assisted Writing and Document Intelligence", "5", 1),
    ("Large Language Models in Text Generation and Rewriting", "6", 1),
    ("Version Control and Document History Systems", "7", 1),
    ("Real-Time Collaborative Editing", "8", 1),
    ("Role-Based Access Control in Web Applications", "9", 1),
    ("Existing AI Writing Assistant Systems", "10", 1),
    ("Summary and Research Gaps", "11", 1),
    ("Research Methodology", "12", 0),
    ("Overview of Research Methodology", "12", 1),
    ("Design Science Research (DSR) Framework", "13", 1),
    ("Phase 1: Backend Foundation (API, Auth, and Database Design)", "14", 1),
    ("Phase 2: Rich-Text Editor and Version Control", "15", 1),
    ("Phase 3: AI Assistance and Persistent Suggestions", "17", 1),
    ("Phase 4: Collaboration and Evaluation Instrumentation", "19", 1),
    ("Ethical AI Considerations", "21", 1),
    ("System Architecture and Design", "22", 0),
    ("Overview", "22", 1), ("System Architecture", "22", 1),
    ("Backend Service Architecture", "24", 1),
    ("AI Action Service Design", "26", 1),
    ("Database Schema Design", "28", 1),
    ("Safety and Control Mechanisms", "32", 1),
    ("Concurrency Control and Version History", "33", 1),
    ("Real-Time Collaboration", "35", 1),
    ("API Design and Integration", "37", 1),
    ("Sequence Diagram", "41", 1), ("Screenshots", "42", 1),
    ("Frontend Design and Implementation", "43", 0),
    ("Overview", "43", 1), ("Technology Stack and Design Choices", "43", 1),
    ("Core Frontend Features", "45", 1),
    ("Data Flow Between Frontend and Backend", "51", 1),
    ("Evaluation and Results", "52", 0),
    ("Testing", "52", 1), ("Performance Evaluation", "54", 1),
    ("Usability Evaluation", "55", 1), ("Productivity Evaluation", "56", 1),
    ("Document Quality Analysis", "57", 1), ("Evaluation Results", "57", 1),
    ("Data Collection and Evaluation Methodology", "58", 0),
    ("Overview", "58", 1), ("Evaluation Instruments", "58", 1),
    ("Evaluation Scripts", "60", 1), ("Statistical Analysis", "61", 1),
    ("Data Security and Ethical Considerations", "62", 1),
    ("Future Enhancements", "63", 0),
    ("Multi-Process Pub/Sub for Real-Time Collaboration", "63", 1),
    ("Full-Text Search and Pagination", "64", 1),
    ("CRDT-Based Conflict-Free Collaboration", "64", 1),
    ("Proactive Contextual Suggestions", "65", 1),
    ("Integration with External Writing Platforms", "65", 1),
    ("Conclusions and Recommendations", "66", 0),
    ("Conclusions", "66", 1), ("Recommendations", "67", 1),
    ("Appendices", "68", 0),
    ("Appendix A: Sample AI Action Interactions", "68", 1),
    ("Appendix B: Evaluation and Testing Records", "69", 1),
    ("Appendix C: Ethical Compliance and User Privacy", "70", 1),
    ("Appendix D: Supporting Resources", "70", 1),
    ("References", "71", 0), ("Glossary", "73", 0),
    ("Name", "75", 0),
    ("Checklist of Items for the Final Dissertation / Project / Project "
     "Work Report", "76", 0),
]
toc_table = doc.add_table(rows=0, cols=2)
for title, page, level in toc:
    row = toc_table.add_row().cells
    p0 = row[0].paragraphs[0]
    p0.add_run(("    " * level) + title)
    p1 = row[1].paragraphs[0]
    p1.add_run(page)
    p1.alignment = WD_ALIGN_PARAGRAPH.RIGHT

# ---- end of front-matter section: roman numbering ----
new_section_break("lowerRoman", 1)

# ==================================================================
# BODY (arabic numbering restarts at 1)
# ==================================================================

# ------------------------------------------------------------------
# 1. Introduction
# ------------------------------------------------------------------
h1("Introduction")
h3("Project Objectives")
body("The primary objective of this project is to design and develop "
     "DocIntel AI, an AI-assisted document editor with built-in version "
     "control, real-time collaboration, and evaluation instrumentation. "
     "The system allows users to write and format documents in a rich-text "
     "editor, receive AI-powered writing assistance, save and restore "
     "versions, and collaborate with other users through role-based access "
     "control. A metrics collection framework is integrated to support "
     "academic evaluation of how AI assistance affects writing behaviour.")
body("The specific objectives of the project are as follows:")
numbered([
    "To design and implement a backend using FastAPI that integrates a "
    "pluggable AI provider layer (OpenAI-compatible or local Ollama), "
    "Cloud Firestore for document storage, and Firebase Authentication for "
    "secure identity verification on every request.",
    "To develop an interactive frontend using Angular with a "
    "TipTap/ProseMirror rich-text editor, enabling users to write, format, "
    "and refine documents with AI-powered actions including rewrite, "
    "grammar correction, tone adjustment, continuation, outline "
    "generation, and summarization.",
    "To implement a version control system with atomic optimistic "
    "revision checks, automatic checkpoints, manual snapshots, "
    "transactional restore, and character-level diff comparison, so that "
    "no edit is lost and concurrent writes are safely detected.",
    "To build a real-time collaboration layer using WebSocket-based "
    "presence detection, remote cursor sharing, and live document update "
    "broadcasting, with role-based access control (owner/editor/viewer) "
    "enforced on every backend endpoint.",
    "To implement persistent AI suggestions as a stored workflow where "
    "AI-generated recommendations can be filtered, accepted, or rejected "
    "with revision-aware conflict checks, and acceptance modifies the "
    "document through an explicit editor transaction.",
    "To develop an evaluation instrumentation framework including backend "
    "latency metrics, frontend keystroke and action counters, and analysis "
    "scripts for usability, productivity, and document quality, enabling "
    "rigorous study of AI-assisted writing.",
])
body("By achieving these objectives, the project aims to bridge the gap "
     "between consumer AI writing tools and research-grade writing "
     "platforms that are both practical to use and measurable for academic "
     "study.")

h3("Scope of the Work")
body("The scope of this project spans full-stack engineering, AI-assisted "
     "writing, concurrency control, and interface design.")
table(
    ["Architecture Layer", "Technical Scope", "Key Deliverables"],
    [
        ["Backend & Core Engine",
         "RESTful APIs via FastAPI, ProseMirror JSON document model, "
         "optimistic revision (CAS) transactions, Cloud Firestore "
         "integration.",
         "Document and version repositories, transactional save/restore "
         "engines, safe export serializers (Markdown, HTML, text, DOCX, "
         "PDF)."],
        ["AI Pipeline",
         "Pluggable LLM provider abstraction (OpenAI-compatible / Ollama), "
         "bounded-context prompt assembly, streaming delta/done/error "
         "protocol, output cleaning.",
         "Eleven context-aware AI actions, persistent suggestion "
         "lifecycle, structured title generation."],
        ["Frontend Interface",
         "Modern web application using Angular, TypeScript, and the "
         "TipTap/ProseMirror rich-text editing framework.",
         "Page-first editor workspace, diff visualization, version "
         "timeline, AI inspector panel, live preview of AI output."],
        ["Collaboration & Security",
         "Firebase ID token authentication, role-based access control "
         "(owner/editor/viewer), WebSocket presence and remote cursors.",
         "Share dialog, collaborator management, presence indicator, "
         "revision-conflict recovery."],
        ["Evaluation & Testing",
         "Unit and functional test suites, latency benchmarking, "
         "usability scoring, productivity and document-quality analysis.",
         "Comprehensive test suite, performance metrics collection, "
         "SUS-based usability instruments."],
    ],
)
body("The application focuses on professional and academic document "
     "authoring workflows. It is designed to assist writers in organizing, "
     "refining, and auditing content, but does not autonomously apply "
     "AI-generated output without explicit human review and acceptance.")

h3("Significance and Expected Outcome")
body("The proposed system holds technological, research, and practical "
     "value.")
h5("Technological Significance:")
body("The project demonstrates the integration of LLM-based AI assistance, "
     "optimistic concurrency control, real-time collaboration, and "
     "structured document versioning into a single platform. The pluggable "
     "provider abstraction allows switching between cloud-based and local "
     "models, making the system adaptable to different deployment and "
     "privacy requirements. The implementation of atomic revision checks "
     "within Firestore transactions shows how a NoSQL document store can "
     "support safe concurrent editing without traditional relational "
     "database locking.")
h5("Research Significance:")
body("Unlike commercial AI writing tools that operate as black boxes, "
     "DocIntel AI is instrumented at every layer, recording backend "
     "latency, frontend keystroke counts, AI action types, suggestion "
     "acceptance rates, and session duration. This gives researchers the "
     "data needed to study the impact of AI on writing behaviour. The "
     "included evaluation scripts (SUS scoring, readability analysis, "
     "grammar checking, productivity analysis) establish a reproducible "
     "methodology for academic evaluation.")
h5("Practical Significance:")
body("The system gives users a document editing experience that combines "
     "a word processor with an AI assistant. Users keep full control over "
     "AI output through a preview-only workflow. AI suggestions are never "
     "auto-applied; they must be explicitly inserted, replaced, copied, or "
     "discarded. The version history ensures every change is recoverable, "
     "and the collaboration layer allows multiple users to work on the "
     "same document with clear role boundaries.")
h5("Expected Outcomes:")
bullets([
    "A fully functional AI-assisted document editing platform with both "
    "backend and frontend implementations.",
    "A safe, preview-only AI integration where users explicitly control "
    "whether AI output is applied.",
    "A version control system with automatic checkpoints, manual "
    "snapshots, transactional restore, and character-level diff.",
    "A real-time collaboration layer with presence detection, remote "
    "cursors, and role-based access control.",
    "A persistent suggestion system with revision-aware acceptance and "
    "conflict detection.",
    "An evaluation instrumentation framework with metrics collection, "
    "analysis scripts, and statistical methods.",
    "Quantitative and qualitative evaluation of the system's impact on "
    "writing productivity and document quality.",
])
page_break_clean()

# ------------------------------------------------------------------
# 2. Literature Review
# ------------------------------------------------------------------
h1("Literature Review")
h3("AI-Assisted Writing and Document Intelligence")
body("AI-assisted writing has grown from simple spell checkers and grammar "
     "tools into systems that can rewrite, extend, and restructure text. "
     "Traditional writing aids relied on rule-based methods and "
     "statistical classifiers, which could catch surface errors but had "
     "little understanding of context, intent, or style. The introduction "
     "of neural language models changed this significantly.")
body("Modern AI writing assistants can perform tasks ranging from grammar "
     "correction to tone adjustment, summarization, and stylistic "
     "rewriting. These capabilities are powered by transformer-based "
     "language models pre-trained on large text corpora. In document "
     "editing, AI assistance raises practical questions: does it improve "
     "productivity, does it improve quality, and how should its output be "
     "integrated into the writing workflow. Existing studies have explored "
     "AI-assisted writing in academic and creative contexts, but few "
     "platforms combine AI assistance with rigorous version control, "
     "collaboration, and evaluation instrumentation. This is the gap "
     "DocIntel AI addresses.")

h3("Large Language Models in Text Generation and Rewriting")
body("Large Language Models (LLMs) represent the current state of the art "
     "in text generation. Based on the transformer architecture introduced "
     "by Vaswani et al. (2017), models such as GPT (Brown et al., 2020), "
     "BERT (Devlin et al., 2019), and LLaMA (Touvron et al., 2023) have "
     "shown strong capabilities in understanding and producing human-like "
     "text.")
body("In writing assistance, LLMs are used for several tasks:")
bullets([
    "Rewriting and paraphrasing existing text while preserving meaning.",
    "Grammar and style correction.",
    "Text expansion and continuation.",
    "Summarization of longer passages.",
    "Outline generation for structured documents.",
])
body("A key challenge in using LLMs for editing is controlling the "
     "output. Models can hallucinate content, echo prompt labels back "
     "into the response, or produce text that does not match the user's "
     "intent. Prompt engineering, output cleaning, and structured "
     "validation are common mitigation techniques. In this project, a "
     "bounded-context prompt assembly approach is used, and a cleaning "
     "step strips echoed context labels from provider output.")
body("Another practical consideration is the choice between cloud-based "
     "and local models. Cloud APIs offer higher quality but raise privacy "
     "and cost concerns, while local models (for example, Ollama running "
     "LLaMA) offer privacy and cost benefits with some quality trade-off. "
     "DocIntel AI supports both through a pluggable provider abstraction.")

h3("Version Control and Document History Systems")
body("Version control is a core feature of collaborative document "
     "editing. Traditional word processors provide basic snapshot and "
     "restore features (for example, Word's Track Changes or Google Docs' "
     "version history), but these are generally less rigorous than "
     "software version control systems such as Git, which support "
     "branching, merging, and conflict resolution on plain text.")
body("In web-based editors, document content is usually stored as "
     "structured JSON rather than plain text, which makes traditional "
     "diff and merge techniques harder to apply directly. A common "
     "approach is to store snapshots and compute diffs on the text "
     "representation of the document.")
body("A central problem is concurrency control when multiple users edit "
     "at the same time. Optimistic concurrency using compare-and-swap is "
     "a standard solution: each document carries a revision number, and a "
     "write is accepted only if the client's expected revision matches "
     "the server's current revision. If they do not match, the write is "
     "rejected and the client must reconcile. DocIntel AI implements this "
     "inside Firestore transactions so that two concurrent writes from "
     "the same base revision cannot both commit.")

h3("Real-Time Collaborative Editing")
body("Real-time collaborative editing lets multiple users edit the same "
     "document simultaneously and see each other's activity. Google Docs, "
     "Microsoft Office Online, and Notion are well-known examples.")
body("Two main technical approaches exist:")
bullets([
    "Operational Transformation (OT): concurrent edits are transformed "
    "against each other to maintain consistency. Used by Google Docs; "
    "requires a central sequencer.",
    "Conflict-free Replicated Data Types (CRDTs): operations are "
    "designed to be commutative so that replicas converge without "
    "coordination. Used by Yjs and similar libraries.",
])
body("Both approaches are complex to implement correctly. For an initial "
     "research prototype, a simpler design is to use WebSocket-based "
     "presence and live update broadcasting without automatic merge: "
     "users see each other's cursors and are notified when someone saves, "
     "but concurrent saves produce an explicit revision conflict that is "
     "resolved manually. DocIntel AI takes this approach, trading "
     "automatic merge for transparency and simpler reasoning about data "
     "loss.")

h3("Role-Based Access Control in Web Applications")
body("Role-Based Access Control (RBAC) is the standard model for managing "
     "permissions in multi-user applications. In collaborative document "
     "editing the typical roles are owner (full control), editor (read "
     "and write), and viewer (read only). Enforcement belongs at the API "
     "layer, where each request is authenticated and the caller's role "
     "for the requested resource is checked before the operation "
     "proceeds.")
body("Implementing RBAC on a NoSQL database such as Firestore adds some "
     "difficulty because there are no foreign keys or joins. The "
     "application must enforce relationships itself, for example by "
     "maintaining a collaborators collection and merging owned and "
     "shared documents when listing a user's files. DocIntel AI "
     "centralizes these checks in a permissions service that is applied "
     "consistently across document, version, suggestion, and sharing "
     "endpoints.")

h3("Existing AI Writing Assistant Systems")
body("Several AI-powered writing assistants are widely used today:")
bullets([
    "Grammarly provides real-time grammar, spelling, and style "
    "suggestions as a browser extension and standalone editor, but "
    "offers no version control, collaboration, or research "
    "instrumentation.",
    "Notion AI integrates LLM-based writing assistance into the Notion "
    "workspace with summarization and generation features, but it is a "
    "commercial product without evaluation capabilities.",
    "Jasper and Copy.ai focus on marketing content generation from "
    "prompts and lack document versioning and research tooling.",
    "Google Docs with Gemini provides AI suggestions inside a "
    "collaborative editor, but the integration is proprietary and not "
    "instrumented for academic study.",
])
body("These systems show that AI can assist writing, but they also "
     "reveal gaps: weak version control, AI output that is auto-applied "
     "without explicit acceptance, no persistent suggestion lifecycle, "
     "no exposed metrics for studying writing behaviour, and no ability "
     "to swap AI providers for comparison.")

h3("Summary and Research Gaps")
body("The literature shows strong progress in LLM-based text generation, "
     "document versioning, and collaborative editing, but the following "
     "gaps remain:")
bullets([
    "Lack of integrated AI-assisted writing with rigorous version "
    "control: existing AI writing tools either lack versioning or "
    "provide basic snapshots without optimistic concurrency or "
    "transactional restore.",
    "Limited transparency in AI output integration: most assistants "
    "auto-apply or inline AI text without giving users explicit control "
    "over what is accepted and where it goes.",
    "Absence of persistent, revision-aware suggestions: suggestions are "
    "typically ephemeral, with no stored lifecycle, stale detection, or "
    "accept/reject tracking.",
    "No research-grade evaluation instrumentation: commercial tools do "
    "not expose keystroke, action, or acceptance metrics needed to "
    "study AI's impact on writing.",
    "Inadequate pluggability of AI providers: most systems lock users "
    "into one provider, preventing controlled comparison.",
])
body("The proposed system addresses these gaps through:")
bullets([
    "Integration of AI actions with atomic optimistic revision control, "
    "automatic checkpoints, and transactional restore in one platform.",
    "A preview-only AI workflow where output is never auto-applied and "
    "the user explicitly inserts, replaces, copies, regenerates, or "
    "discards it.",
    "Persistent suggestions with document revision tracking, "
    "stale-revision detection, and an explicit accept/reject/delete "
    "lifecycle.",
    "Evaluation instrumentation at both backend and frontend layers "
    "with standardized analysis scripts.",
    "A pluggable AI provider abstraction supporting OpenAI-compatible "
    "and Ollama models.",
])
page_break_clean()

# ------------------------------------------------------------------
# 3. Research Methodology
# ------------------------------------------------------------------
h1("Research Methodology")
h3("Overview of Research Methodology")
body("This research follows the Design Science Research (DSR) paradigm, "
     "which emphasizes the creation and evaluation of innovative "
     "artifacts to solve real-world problems through systematic design "
     "and iterative improvement. The project combines software "
     "engineering, human-computer interaction, and applied artificial "
     "intelligence, and DSR provides a suitable framework to guide both "
     "the technical development and the scientific validation of the "
     "system.")
body("According to Hevner et al. (2004), Design Science involves three "
     "key components:")
bullets([
    "Design and build: creation of an artifact, in this case the "
    "DocIntel AI platform.",
    "Evaluate: assessment of the artifact's performance, utility, and "
    "contribution.",
    "Knowledge contribution: insights that advance both research and "
    "practice.",
])
body("The iterative DSR cycle adopted in this work is:")
body("Problem Identification -> Design -> Build -> Evaluation -> "
     "Refinement")
body("Each iteration improves the artifact's technical performance, "
     "collaboration safety, and user experience.")

h3("Design Science Research (DSR) Framework")
body("The research process was divided into four structured phases, each "
     "containing design, development, and evaluation activities.")
fig("Figure 3.1: DSR Framework.")

h3("Phase 1: Backend Foundation (API, Auth, and Database Design)")
h4("FastAPI Service Architecture")
body("The first phase established the backend infrastructure using "
     "FastAPI. The backend follows a layered architecture separating "
     "concerns into routers (HTTP endpoints), schemas (Pydantic "
     "request/response validation), domain models (internal "
     "representations), repositories (Firestore data access), services "
     "(business logic such as AI actions, permissions, connection "
     "management, and metrics), and utilities (content validation, diff "
     "computation, export converters).")
body("This layered design keeps the system modular and testable. Each "
     "layer can be tested independently with mocked dependencies, and "
     "individual components can be replaced without affecting the rest "
     "of the system.")
h4("Firebase Authentication and Firestore Database Design")
body("Authentication uses Firebase Authentication with email/password "
     "sign-in. The frontend obtains an ID token from the Firebase JS SDK "
     "and sends it as a bearer token on every API request. The backend "
     "verifies the token with the Firebase Admin SDK and extracts the "
     "user ID for authorization.")
body("The database is Cloud Firestore in Native mode. Firestore is a "
     "NoSQL document store with no foreign keys, joins, or SQL "
     "migrations, so relationships are enforced at the application "
     "level. The initial schema stores TipTap/ProseMirror JSON content "
     "in the documents collection. All data access goes through the "
     "backend; Firestore security rules deny direct client access.")

h3("Phase 2: Rich-Text Editor and Version Control")
h4("TipTap/ProseMirror Editor Integration")
body("The editor is built on TipTap, a headless rich-text framework "
     "over ProseMirror. Content is stored as structured JSON, which "
     "supports programmatic manipulation, multi-format serialization, "
     "and custom extensions. The toolbar supports headings, marks, "
     "lists, links, tables, images, alignment, and page breaks. Custom "
     "extensions handle indentation and page-break display.")
body("TipTap JSON is the canonical storage format. Plain text is "
     "derived only when needed for LLM context, diff computation, or "
     "export.")
h4("Document Schema Validation and Atomic Revision Control")
body("Two mechanisms protect data integrity:")
bullets([
    "Content validation: incoming document JSON is limited to 750 KB, "
    "20,000 nodes, and depth 64, preventing oversized or deeply nested "
    "content from hitting Firestore's 1 MiB limit or breaking recursive "
    "processing.",
    "Optimistic revision control: each document carries an integer "
    "revision (legacy documents default to 0). Every update requires "
    "the client's base_revision; the Firestore transaction compares it "
    "to the current revision and only commits on match, otherwise "
    "returning 409. Word count is computed server-side.",
])

h3("Phase 3: AI Assistance and Persistent Suggestions")
h4("AI Action Service and Prompt Assembly")
body("A bounded-context AI Action Service centralizes prompt assembly "
     "for eleven actions: rewrite, improve, expand, condense, summarize, "
     "grammar, tone, continue, outline, custom, and generate. Each "
     "action has a specification containing the system prompt, whether "
     "selected text is required, and a display label.")
body("Prompt assembly combines the action's system prompt with the "
     "document title and the text before, at, and after the selection "
     "(each trimmed to 4000 characters). This gives the model enough "
     "context to produce relevant output without sending the entire "
     "document. A unified POST /ai/action endpoint handles all actions, "
     "while the earlier rewrite, summarize, and generate endpoints are "
     "preserved for compatibility and delegate to the same service.")
h4("Persistent Suggestion Lifecycle")
body("AI suggestions are stored as first-class entities in a "
     "suggestions collection. Each suggestion records its type, "
     "original text, suggested text, reason, document revision, status "
     "(pending/accepted/rejected), and resolver information.")
body("The lifecycle is:")
bullets([
    "Create: the AI output is stored with the current document "
    "revision.",
    "List: users filter suggestions by status.",
    "Accept: requires the current base_revision; a stale document "
    "returns 409. The frontend applies the change through an editor "
    "transaction.",
    "Reject: does not require a revision check.",
    "Delete: removes the suggestion.",
])
h4("AI Output Cleaning and Safety")
body("A clean_writing() step strips echoed context labels (such as "
     "'Document title:' or 'Selected text:') that providers sometimes "
     "copy into their output. The streaming generate endpoint buffers "
     "the stream, cleans the joined text, and emits a single delta "
     "capped at 50,000 characters so partial or labelled chunks never "
     "reach the editor. Structured outputs such as title suggestions "
     "are validated with Pydantic models before being returned.")

h3("Phase 4: Collaboration and Evaluation Instrumentation")
h4("Role-Based Access Control")
body("A documentCollaborators collection links users to documents with "
     "a role (owner, editor, or viewer). A permissions service provides "
     "require_owner, require_editor, and require_viewer checks, applied "
     "consistently across document, version, suggestion, and sharing "
     "endpoints. Listing documents merges owned and shared items. "
     "Invites are sent by email; the backend resolves the email to a "
     "user and rejects self-shares, owner-role invites, unknown users, "
     "and invalid addresses.")
h4("WebSocket Presence and Remote Cursors")
body("A WebSocket endpoint at /ws/documents/{id} authenticates via "
     "token query parameter and checks viewer access. An in-memory "
     "connection manager tracks connections per document and broadcasts "
     "presence, document_updated, version_created, and cursor events. "
     "On the frontend, a WebSocket service auto-reconnects and exposes "
     "signals for presence, updates, and remote cursors, which are "
     "rendered through a TipTap extension as coloured carets and "
     "selection highlights.")
h4("Evaluation Instrumentation")
body("A metrics middleware records per-request latency on the backend, "
     "and a metrics collector service exposes p50/p95 summaries, recent "
     "records, and reset. On the frontend, an opt-in metrics collector "
     "counts keystrokes, AI actions by type, suggestion accept/reject "
     "events, version operations, document opens, share invites, "
     "exports, and session duration, with JSON export for analysis. "
     "Evaluation scripts cover load testing, readability and grammar "
     "comparison, SUS scoring, and productivity analysis.")

h3("Ethical AI Considerations")
body("Ethics and user control guided the implementation:")
bullets([
    "Preview-only AI: generated output is never auto-applied; the user "
    "explicitly inserts, replaces, copies, regenerates, or discards it.",
    "User data protection: all data access flows through the "
    "authenticated backend, and Firestore rules deny direct client "
    "access.",
    "Test isolation: tests use mocked Firebase and AI providers; no "
    "live credentials or production data are touched by the test suite.",
    "Transparency: AI actions and suggestions are recorded with type, "
    "reason, and status, giving users a clear audit trail of AI "
    "involvement.",
    "Non-destructive versioning: checkpoints, snapshots, and restores "
    "are additive; the system never deletes history.",
])
page_break_clean()

# ------------------------------------------------------------------
# 4. System Architecture and Design
# ------------------------------------------------------------------
h1("System Architecture and Design")
h3("Overview")
body("This chapter presents the architecture and design of DocIntel AI. "
     "The system integrates a FastAPI backend with pluggable AI "
     "providers, Cloud Firestore for persistence, Firebase "
     "Authentication for identity, a WebSocket layer for real-time "
     "collaboration, and an Angular frontend with a TipTap rich-text "
     "editor. The design focuses on modularity, data integrity, "
     "explicit user control over AI output, and evaluation "
     "instrumentation.")

h3("System Architecture")
body("The system consists of five major layers:")
bullets([
    "User Interface Layer (Angular frontend).",
    "API Gateway Layer (FastAPI backend).",
    "AI Service Layer (action service and provider abstraction).",
    "Real-Time Communication Layer (WebSocket connection manager).",
    "Data Persistence Layer (Cloud Firestore).",
])
body("The user interacts with a page-first editor that communicates "
     "with the backend over HTTP and WebSocket. The backend handles "
     "authentication, authorization, document and version management, "
     "AI actions, suggestions, sharing, and realtime events. AI "
     "requests go through the action service to the configured "
     "provider, and all data persists in Firestore.")
fig("Figure 4.1: Overall System Architecture of DocIntel AI.")

h3("Backend Service Architecture")
h4("Routers, Schemas, and Domain Models")
body("The backend separates HTTP handling into routers (documents, "
     "versions, suggestions, sharing, AI, analytics, metrics, users, "
     "health, websocket), validation into Pydantic schemas, internal "
     "representations into domain models, and data access into "
     "repositories. Business logic lives in services: ai_actions for "
     "prompt assembly, ai_provider for the LLM abstraction, "
     "permissions for RBAC, connection_manager for WebSocket tracking, "
     "and metrics_collector for latency statistics.")
h4("Repository Pattern and Firestore Data Access")
body("Repositories encapsulate all Firestore operations behind a "
     "clean interface, which makes the endpoints easy to test with "
     "mocked repositories. Synchronous Firestore SDK calls are run in "
     "the FastAPI threadpool so they do not block the async event "
     "loop, and SDK initialization is guarded by a lock for "
     "concurrent requests.")
h4("Pluggable AI Provider Abstraction")
body("The provider layer supports two backends selected by the "
     "AI_PROVIDER setting: an OpenAI-compatible API (configurable key, "
     "base URL, model) and a local Ollama instance (base URL and "
     "model). Both streaming and non-streaming generation are "
     "supported. For streaming, the endpoint negotiates an NDJSON "
     "protocol with delta, done, and error frames, and the provider "
     "reader detects missing termination so partial failures are not "
     "swallowed as successful completions.")

h3("AI Action Service Design")
h4("Bounded-Context Prompt Assembly")
body("Each of the eleven actions has a specification with a system "
     "prompt, a needs_text flag, and a label. The build_prompt() "
     "function combines the system prompt with the document title and "
     "the before/selection/after context (each trimmed to 4000 "
     "characters), plus optional parameters such as tone or a custom "
     "instruction. This keeps token usage bounded while giving the "
     "model relevant context.")
h4("Streaming Delta/Done/Error Protocol")
body("Streaming uses NDJSON frames: delta for text chunks, done for "
     "the final result, and error for failures. The frontend requires "
     "a done frame before treating generation as successful; a stream "
     "that ends early is rejected as partial output rather than "
     "applied as a result.")
h4("Output Cleaning and Structured Validation")
body("clean_writing() removes context labels that providers echo "
     "back. Structured outputs such as title suggestions return 3-5 "
     "options as validated JSON and update only the document title, "
     "never the body.")

h3("Database Schema Design")
body("The system uses Cloud Firestore with five top-level "
     "collections. Relationships are enforced at the application "
     "level, and schema changes are additive so legacy records keep "
     "working with safe defaults.")
h4("Users Collection")
body("users/{uid}")
table(["Field", "Type", "Description"], [
    ["name", "string", "Display name"],
    ["email", "string", "Email address"],
    ["createdAt", "timestamp", "Account creation time"],
    ["lastLoginAt", "timestamp", "Last login time"],
])
h4("Documents Collection")
body("documents/{id}")
table(["Field", "Type", "Description"], [
    ["ownerId", "string", "Firebase UID of the owner"],
    ["title", "string", "Document title"],
    ["content", "map", "TipTap/ProseMirror JSON content"],
    ["wordCount", "int", "Server-computed word count"],
    ["revision", "int", "Optimistic revision number (CAS)"],
    ["updatedBy", "string", "UID of the last updater"],
    ["lastCheckpointAt", "timestamp", "Last automatic checkpoint time"],
    ["createdAt / updatedAt", "timestamp", "Timestamps"],
])
h4("Versions Collection")
body("versions/{id}")
table(["Field", "Type", "Description"], [
    ["documentId", "string", "Parent document"],
    ["ownerId", "string", "Document owner UID"],
    ["title / content / wordCount", "-", "Snapshot of the document "
     "state"],
    ["label", "string", "User-provided label for manual snapshots"],
    ["source", "string", "manual | autosave | before_restore | "
     "restore"],
    ["createdBy / authorName", "string", "Actor identity"],
    ["documentRevision", "int", "Document revision at snapshot time"],
    ["restoredFromVersionId", "string", "Source version for restores"],
    ["createdAt", "timestamp", "Creation time"],
])
h4("Suggestions Collection")
body("suggestions/{id}")
table(["Field", "Type", "Description"], [
    ["documentId", "string", "Parent document"],
    ["type", "string", "Suggestion type (rewrite, grammar, tone, ...)"],
    ["originalText / suggestedText", "string", "Before and after "
     "text"],
    ["reason", "string", "Explanation for the suggestion"],
    ["status", "string", "pending | accepted | rejected"],
    ["documentRevision", "int", "Revision at creation (stale check)"],
    ["resolvedBy / createdBy", "string", "Resolver and creator UIDs"],
    ["createdAt", "timestamp", "Creation time"],
])
h4("Document Collaborators Collection")
body("documentCollaborators/{id}")
table(["Field", "Type", "Description"], [
    ["documentId", "string", "Shared document"],
    ["userId", "string", "Collaborator UID"],
    ["role", "string", "owner | editor | viewer"],
    ["email / name", "string", "Collaborator display info"],
    ["createdBy", "string", "Inviter UID"],
    ["createdAt", "timestamp", "Invitation time"],
])
fig("Figure 4.2: Firestore Collection Relationships.")

h3("Safety and Control Mechanisms")
body("The system applies several layers of control to keep AI output "
     "safe and the user in charge:")
bullets([
    "Authentication: every endpoint except /health verifies the "
    "Firebase ID token.",
    "Authorization: role checks run on every document, version, "
    "suggestion, and sharing operation (viewer for reads, editor for "
    "writes, owner for destructive and sharing operations).",
    "Preview-only AI: generated text stays in the inspector until the "
    "user explicitly inserts, replaces, copies, or discards it; a "
    "stale-document check refuses to apply output if the document "
    "changed during generation.",
    "Output cleaning: provider output is cleaned of echoed context "
    "labels, and structured outputs are validated before returning.",
    "Export safety: HTML export escapes interpolated values and "
    "filters javascript/data URLs in links.",
    "Test isolation: no test touches live Firebase or provider "
    "credentials.",
])

h3("Concurrency Control and Version History")
h4("Optimistic Revision (CAS) Transactions")
body("Every document update runs inside a Firestore transaction that "
     "checks the client-supplied base_revision against the stored "
     "revision. On match, the transaction detects no-op saves, writes "
     "an automatic checkpoint when due, increments the revision, "
     "computes word count server-side, and updates timestamps and "
     "actor fields. On mismatch, the write is rejected with 409, so "
     "two concurrent saves from the same base cannot both commit.")
h4("Autosave and Conflict Recovery")
body("A per-editor autosave service serializes and coalesces save "
     "requests: one request in flight at a time, queued saves merged "
     "to the latest state. On a 409 the service surfaces a conflict "
     "state and offers retry, draft download, or confirmed reload, "
     "and a leave warning protects unsaved changes. The editor "
     "exposes distinct dirty, saving, saved, failed, and conflict "
     "states.")
h4("Snapshots, Checkpoints, and Restore")
body("Manual snapshots capture the full document state with an "
     "optional label and a revision guard. Automatic checkpoints are "
     "written inside the update transaction: the first changed save "
     "captures the pre-edit state, then at most once every five "
     "minutes thereafter; no-op saves skip both revision and "
     "checkpoint.")
body("Restore is transactional: it validates the request, writes a "
     "before_restore snapshot of the current state, applies the "
     "target version, writes a restore snapshot recording the source "
     "version, and resets the checkpoint timer. A character-level "
     "diff endpoint compares any version against the current "
     "document or another version and returns "
     "equal/insert/delete/replace chunks for the diff viewer.")

h3("Real-Time Collaboration")
body("An in-memory connection manager tracks WebSocket connections "
     "per document and broadcasts presence, presence_list, "
     "document_updated, version_created, and cursor events. The "
     "update, create-version, and restore endpoints broadcast after "
     "committing so connected clients refresh automatically. Cursor "
     "messages carry selection ranges and are forwarded to every "
     "other connected user; the frontend renders them as coloured "
     "carets and selection highlights through a TipTap extension, "
     "and removes cursors for users who disconnect.")
fig("Figure 4.3: Real-Time Collaboration Flow.")

h3("API Design and Integration")
body("All endpoints except /health require a Firebase bearer token. "
     "The main endpoint groups are:")
bullets([
    "GET /health - service health check.",
    "GET /users/me - provisions and returns the user profile.",
    "GET/POST /documents; GET/PATCH/DELETE /documents/{id} - document "
    "CRUD; PATCH requires base_revision and returns revision, "
    "updated_by, owner_id.",
    "GET/POST /documents/{id}/versions; GET/DELETE "
    ".../versions/{vid}; GET .../diff?compare_to=...; POST "
    ".../restore - version management, diff, and transactional "
    "restore.",
    "GET /ai/actions; POST /ai/action - action discovery and unified "
    "AI endpoint; POST /ai/rewrite, /ai/summarize, /ai/generate "
    "preserved for compatibility, generate streams NDJSON.",
    "GET/POST /documents/{id}/suggestions; PATCH/DELETE "
    ".../suggestions/{sid} - suggestion lifecycle with "
    "revision-aware acceptance.",
    "GET/POST /documents/{id}/collaborators; DELETE "
    ".../collaborators/{cid} - sharing management.",
    "GET /analytics; GET /documents/{id}/stats, /evaluate, "
    "/export?format=markdown|html|text|docx|pdf - analytics and "
    "export.",
    "GET /metrics/summary, /metrics/recent; POST /metrics/reset - "
    "latency metrics.",
    "WS /ws/documents/{id} - realtime presence, cursor, and update "
    "events.",
])
body("Example response from POST /ai/action:")
body('{ "output": "Here is a cleaner version of your paragraph..." }')
body("Example conflict response from PATCH /documents/{id}:")
body('{ "detail": "Document has been modified. Expected revision 4, '
     'found 6." }')

h3("Sequence Diagram")
body("The sequence of an AI-assisted edit: the user selects text and "
     "picks an action; the frontend posts to /ai/action with the text "
     "and surrounding context; the backend assembles the prompt and "
     "calls the provider; the preview appears in the inspector; on "
     "Insert or Replace the frontend applies the text and autosaves "
     "through PATCH with base_revision; the transaction validates "
     "the revision and commits; the backend then broadcasts "
     "document_updated to collaborators over WebSocket.")
fig("Figure 4.4: Sequence Diagram for AI-Assisted Editing Flow.")

h3("Screenshots")
fig("Figure 4.5: Dashboard with Document Grid, Search, and Filters.")
fig("Figure 4.6: Page-First Editor Workspace with AI Inspector.")
fig("Figure 4.7: Version History Timeline with Diff Comparison.")
fig("Figure 4.8: Share Dialog and Presence Indicator.")
page_break_clean()

# ------------------------------------------------------------------
# 5. Frontend Design and Implementation
# ------------------------------------------------------------------
h1("Frontend Design and Implementation")
h3("Overview")
body("The frontend provides the user-facing layer of the system: a "
     "dashboard for document management and a page-first editor "
     "workspace with AI assistance, suggestions, version history, "
     "and collaboration. It is built in Angular using standalone "
     "components, signals for state, Angular Material for UI, and "
     "TipTap for the editor.")

h3("Technology Stack and Design Choices")
h4("Angular and Standalone Components")
body("Angular's standalone components remove NgModule overhead and "
     "enable lazy-loaded routes. Signals provide fine-grained "
     "reactivity for UI state such as save status, presence, and "
     "suggestion lists, while RxJS handles HTTP and form values.")
h4("Angular Material and Design Tokens")
body("Angular Material supplies accessible components (buttons, "
     "cards, dialogs, chips, tabs, form fields). A custom theme and "
     "--docintel-* design tokens keep spacing, colours, and "
     "typography consistent.")
h4("TipTap / ProseMirror")
body("TipTap provides the rich-text core with content stored as "
     "ProseMirror JSON. Custom extensions implement page breaks, "
     "indentation control, and remote cursor decorations.")
h4("Firebase JS Auth")
body("The Firebase client SDK is used for authentication only. The "
     "frontend never talks to Firestore directly; all application "
     "data flows through the backend API.")

h3("Core Frontend Features")
h4("Application Shell and Routing")
body("An app shell wraps authenticated routes with a collapsible "
     "sidebar containing navigation, a new-document button, an "
     "account menu, and an evaluation metrics section. On small "
     "screens the sidebar becomes an overlay with a floating menu "
     "button. Auth and guest guards protect routes, and an HTTP "
     "interceptor attaches the Firebase ID token, checking origin "
     "and path boundaries to avoid leaking tokens to other "
     "origins.")
fig("Figure 5.1: Application Shell with Collapsible Sidebar.")
h4("Authentication (Login and Register)")
body("Login and register pages use Material form components and "
     "display Firebase errors in user-friendly messages. "
     "Registration provisions the user profile via GET /users/me "
     "before navigating to the dashboard.")
fig("Figure 5.2: User Login and Register Interface.")
h4("Dashboard")
body("The dashboard lists all accessible documents (owned and "
     "shared) as cards with real-time search, All/Owned/Shared "
     "filter tabs with counts, sorting by updated time, title, or "
     "word count, shared-document badges, and empty states. Writing "
     "analytics charts summarise document counts and activity.")
fig("Figure 5.3: Dashboard with Document Grid and Analytics.")
h4("Page-First Editor Workspace")
body("The editor is presented as a word processor: a grey canvas "
     "with a centred white A4-like page, a compact title/save row "
     "(with save-state indicator, share, export, and version "
     "controls), a grouped formatting toolbar, and an inspector "
     "panel with AI, Suggestions, History, and Stats tabs that "
     "collapses to give the page more space. On mobile the "
     "inspector becomes an overlay.")
fig("Figure 5.4: Page-First Editor Workspace.")
h4("AI Assistant Integration")
body("The AI tab offers eleven actions: rewrite, improve, expand, "
     "condense, summarize, grammar, tone (with a tone selector), "
     "continue, outline, custom, and generate. The request sends "
     "the selected text plus surrounding context and the document "
     "title. Output is preview-only: the user explicitly chooses "
     "Insert at cursor, Insert below, Replace selection, Copy, "
     "Regenerate, or Discard.")
body("The original selection is pinned when the request starts; if "
     "the document changes during generation the apply is refused. "
     "Generation streams into the preview, can be stopped, and a "
     "stream that ends without a done frame is rejected as partial "
     "output rather than applied.")
fig("Figure 5.5: AI Panel with Preview-Only Output.")
h4("Persistent Suggestions UI")
body("The Suggestions tab shows suggestions with "
     "pending/accepted/rejected filter chips and counts, each entry "
     "displaying type, original text, suggested text, and reason. "
     "Accept sends the current base_revision; a stale document "
     "returns a 409 message. On accept, the matched passage is "
     "replaced through an editor transaction and persisted by "
     "autosave. Accept is blocked while the document has unsaved "
     "changes.")
fig("Figure 5.6: Suggestion List with Filters and Actions.")
h4("Version History and Diff")
body("The History tab shows a compact timeline with source labels "
     "(Manual snapshot, Automatic checkpoint, Before restore, "
     "Restored) and friendly author names. Selecting a version "
     "offers compare and restore actions: compare shows a "
     "character-level diff between the current document and a "
     "snapshot or between two snapshots, and restore asks for "
     "confirmation and locks editing while it runs.")
fig("Figure 5.7: Version History Timeline with Diff.")
h4("Sharing and Collaboration UI")
body("The share dialog lets the owner invite collaborators by "
     "email with an editor or viewer role, and lists existing "
     "collaborators with remove buttons. Backend validation "
     "errors (self-share, unknown user, invalid email) are shown "
     "in the dialog. The editor header shows a presence indicator "
     "when collaborators are connected, and remote cursors appear "
     "as coloured carets with name labels.")
fig("Figure 5.8: Share Dialog and Remote Cursors.")
h4("Export, Statistics, and Responsive Design")
body("An export menu offers Markdown, HTML, text, DOCX, and PDF "
     "downloads. The Stats tab shows word count and readability "
     "metrics. The layout is responsive: multi-column grids "
     "collapse on tablet, the sidebar and inspector become "
     "overlays on mobile, toolbar buttons are touch-friendly, "
     "and the inspector can be resized by keyboard as well as "
     "mouse.")

h3("Data Flow Between Frontend and Backend")
body("Each user interaction follows the same pattern:")
bullets([
    "The user acts (types, selects text, runs an AI action, "
    "accepts a suggestion, saves a version, or shares).",
    "The frontend updates local signals and the UI immediately.",
    "An HTTP request goes to the backend with the Firebase ID "
    "token.",
    "The backend verifies the token, checks authorization, "
    "performs the operation, and returns a response.",
    "The frontend updates state and UI from the response.",
    "For document saves, version creation, and cursor moves, "
    "the backend broadcasts a WebSocket event so other connected "
    "clients update in real time.",
])
page_break_clean()

# ------------------------------------------------------------------
# 6. Evaluation and Results
# ------------------------------------------------------------------
h1("Evaluation and Results")
h3("Testing")
h4("Unit Testing (Backend)")
body("The backend is tested with pytest and FastAPI's TestClient "
     "using mocked Firebase and AI providers; no test contacts live "
     "services. The suite covers authentication, document CRUD with "
     "role checks, revision conflict detection and checkpoint "
     "logic, version CRUD/diff/restore, ACLs on versions and "
     "suggestions, AI action and provider behaviour including "
     "stream errors and output cleaning, suggestion lifecycle with "
     "stale-revision handling, sharing invites and removals, "
     "WebSocket presence and broadcasts, metrics recording, "
     "analytics aggregation, and export converters.")
body("Backend test count: 202 tests passing.")
h4("Unit Testing (Frontend)")
body("The frontend is tested with Vitest through the Angular test "
     "builder. Tests cover the app shell, auth interceptor, AI "
     "service (including streaming and errors), autosave service "
     "(serialization, coalescing, conflict handling), WebSocket "
     "service, metrics collector, sharing and suggestion "
     "services, the dashboard, the editor, AI output preview, "
     "suggestion list, and version history components.")
body("Frontend test count: 88 tests passing.")
h4("Functional Testing")
body("End-to-end flows were exercised manually: create, edit, run "
     "AI actions, apply output, save versions, compare and "
     "restore, accept suggestions, share with collaborators, and "
     "observe presence and remote cursors across two browser "
     "tabs, including revision conflict behaviour when both tabs "
     "save.")

h3("Performance Evaluation")
body("The backend metrics middleware records per-request latency, "
     "and the metrics summary endpoint reports p50 and p95 per "
     "endpoint. Targets: p95 under 500ms for document reads and "
     "writes, and under 1500ms for AI actions. A Locust load-test "
     "script exercises six representative endpoints and "
     "cross-references the metrics summary. The production "
     "frontend build produces an initial bundle of about 233 kB "
     "with the editor lazy-loaded at about 524 kB.")

h3("Usability Evaluation")
body("Usability is measured with the System Usability Scale "
     "(SUS), a 10-item 5-point questionnaire administered after a "
     "scripted task set (register, create a document, write 200+ "
     "words, run three AI actions, handle a suggestion, save and "
     "restore a version, share and view a shared document). "
     "Target: SUS >= 68. Scoring is handled by the "
     "sus_scoring.py script, which reports mean, median, "
     "standard deviation, min, and max.")

h3("Productivity Evaluation")
body("Productivity is measured by a standardized writing task "
     "performed with and without AI assistance: keystroke count "
     "(target: 20%+ reduction with AI), words per minute in a "
     "timed free-writing session (target: 15%+ increase), and "
     "self-reported productivity on a 7-point scale. The "
     "productivity_analysis.py script computes paired t-tests "
     "and Cohen's d effect sizes.")

h3("Document Quality Analysis")
body("Document quality compares pre-AI and post-AI versions on "
     "readability (Flesch-Kincaid via textstat, target: 10%+ "
     "improvement) and grammar error count (via "
     "language_tool_python, target: 30%+ reduction) using the "
     "quality_analysis.py script on a set of sample documents.")

h3("Evaluation Results")
body("The evaluation instruments and scripts are implemented and "
     "verified with template data, but participant data has not "
     "yet been collected. The table below records the targets "
     "and will be populated once the study is conducted.")
table(["Dimension", "Metric", "Target", "Result"], [
    ["Usability", "SUS score", ">= 68", "pending"],
    ["Performance", "Document read/write p95", "< 500 ms", "pending"],
    ["Performance", "AI action p95", "< 1500 ms", "pending"],
    ["Productivity", "Keystroke reduction", ">= 20%", "pending"],
    ["Productivity", "WPM increase", ">= 15%", "pending"],
    ["Quality", "Readability improvement", ">= 10%", "pending"],
    ["Quality", "Grammar error reduction", ">= 30%", "pending"],
])
page_break_clean()

# ------------------------------------------------------------------
# 7. Data Collection and Evaluation Methodology
# ------------------------------------------------------------------
h1("Data Collection and Evaluation Methodology")
h3("Overview")
body("Data collection covers two areas: instrumentation data "
     "recorded automatically during use (request latency, "
     "keystrokes, AI actions, suggestion outcomes) and "
     "evaluation data gathered through scripted tasks and "
     "questionnaires (SUS, WPM, perceived productivity). "
     "Metrics collection is opt-in on the frontend, and no "
     "document content or personally identifying data is "
     "recorded.")

h3("Evaluation Instruments")
h4("Backend Metrics Middleware")
body("A middleware records normalized endpoint, method, status "
     "code, timestamp, and latency for every request. The "
     "metrics collector service exposes p50/p95 summaries, "
     "recent records, and reset, and the metrics endpoints "
     "exclude themselves from recording. No document content "
     "or user-identifying data is stored.")
h4("Frontend Metrics Collector")
body("An opt-in collector counts keystrokes, AI actions by "
     "type, suggestion accepts/rejects, version "
     "saves/restores, document opens and creates, share "
     "invites, exports, and session duration, with JSON "
     "export and reset. The sidebar carries the enable "
     "toggle and export button.")

h3("Evaluation Scripts")
body("Four scripts live in backend/scripts/eval/:")
bullets([
    "load_test.py - Locust configuration exercising six "
    "endpoints and cross-referencing the metrics summary.",
    "quality_analysis.py - readability deltas via textstat "
    "and grammar deltas via language_tool_python for single "
    "pairs or batches.",
    "sus_scoring.py - SUS scoring with positive/negative "
    "item adjustment and aggregate statistics, warning when "
    "n < 15.",
    "productivity_analysis.py - paired t-tests for WPM and "
    "perceived productivity with Cohen's d, using scipy "
    "when available and a normal approximation otherwise.",
])

h3("Statistical Analysis")
body("Within-subject comparisons use paired t-tests when the "
     "sample is large enough, with a Wilcoxon signed-rank "
     "fallback for small or non-normal samples. Effect size "
     "is reported as Cohen's d with significance at alpha = "
     "0.05. Planned minimums: 15 participants for usability "
     "and 30 documents for quality analysis.")

h3("Data Security and Ethical Considerations")
bullets([
    "Anonymity and privacy: metrics contain no document "
    "content or user identifiers; evaluation responses are "
    "stored separately from application data.",
    "Data security: all access flows through the "
    "authenticated backend, Firestore rules deny direct "
    "client access, and secret files are gitignored.",
    "Responsible AI: AI output is preview-only and never "
    "applied without explicit user action, and AI "
    "involvement is auditable through suggestion records.",
])
page_break_clean()

# ------------------------------------------------------------------
# 8. Future Enhancements
# ------------------------------------------------------------------
h1("Future Enhancements")
body("The current system provides a complete editing, "
     "AI-assistance, versioning, and collaboration workflow. "
     "Several realistic extensions remain for future work.")

h3("Multi-Process Pub/Sub for Real-Time Collaboration")
body("The connection manager is in-memory and single-process, "
     "so broadcasts only reach clients connected to the same "
     "server instance. A pub/sub layer (for example Redis) "
     "would let presence and update events cross server "
     "instances, enabling horizontal scaling of the realtime "
     "layer.")

h3("Full-Text Search and Pagination")
body("Document listing currently fetches all accessible "
     "documents and filters in memory. Server-side search and "
     "cursor pagination, backed by composite indexes, would "
     "be needed for larger collections, and could later "
     "extend to full-text search across document content.")

h3("CRDT-Based Conflict-Free Collaboration")
body("Collaboration today uses optimistic locking with "
     "manual conflict resolution. Integrating a CRDT library "
     "such as Yjs would allow concurrent edits to merge "
     "automatically without conflicts, at the cost of added "
     "complexity in the editor integration.")

h3("Proactive Contextual Suggestions")
body("Suggestions currently require an explicit AI action. "
     "A future version could analyse text in the background "
     "and surface grammar or tone suggestions proactively, "
     "with careful UX to avoid being intrusive.")

h3("Integration with External Writing Platforms")
body("For academic workflows, integration with reference "
     "managers such as Zotero or Mendeley, citation "
     "insertion, and export to LaTeX/BibTeX formats would "
     "make the platform more useful to research writers.")
page_break_clean()

# ------------------------------------------------------------------
# 9. Conclusions and Recommendations
# ------------------------------------------------------------------
h1("Conclusions and Recommendations")
h3("Conclusions")
body("This work presented DocIntel AI, an AI-assisted "
     "document editor that combines LLM-based writing help, "
     "structured version control, real-time collaboration, "
     "and evaluation instrumentation in a single full-stack "
     "system.")
body("The main outcomes of the project are:")
bullets([
    "AI-assisted writing with user control: eleven "
    "context-aware actions deliver output through a "
    "preview-only workflow where nothing is applied "
    "without explicit acceptance.",
    "Reliable versioning: optimistic revision checks "
    "inside Firestore transactions prevent lost writes, "
    "automatic checkpoints preserve pre-edit state, and "
    "transactional restore keeps full history.",
    "Real collaboration: owner/editor/viewer access "
    "control, WebSocket presence, remote cursors, and "
    "live update broadcasts support multi-user editing "
    "with explicit conflict handling.",
    "Persistent suggestions: AI recommendations are "
    "stored, filtered, and resolved with revision-aware "
    "checks rather than disappearing after a single "
    "view.",
    "Evaluation instrumentation: latency metrics, "
    "keystroke and action counters, and analysis scripts "
    "provide a reproducible basis for studying "
    "AI-assisted writing.",
])
body("Verification is strong at the unit and build level: "
     "202 backend tests and 88 frontend tests pass and the "
     "production build is clean. Live multi-user behaviour "
     "and the participant evaluation remain the final "
     "steps, with instruments already prepared.")

h3("Recommendations")
body("Based on the results and limitations of this study, "
     "the following directions are recommended:")
bullets([
    "Complete live multi-tab and multi-user verification "
    "of presence, cursors, updates, and conflict "
    "behaviour, then run the participant evaluation "
    "with the prepared instruments.",
    "Scale the realtime layer with multi-process "
    "pub/sub so broadcasts work across server "
    "instances.",
    "Add server-side search and pagination as document "
    "collections grow.",
    "Evaluate CRDT-based merging if seamless concurrent "
    "editing becomes a requirement.",
    "Enrich the suggestion system with proactive, "
    "context-aware recommendations and provider-quality "
    "comparisons using the pluggable abstraction.",
])
page_break_clean()

# ------------------------------------------------------------------
# Appendices / References / Glossary / Checklist
# ------------------------------------------------------------------
h1("Appendices", numbered=False)
h3("Appendix A: Sample AI Action Interactions", numbered=False)
body("The following anonymized examples show how the editor's "
     "AI actions behave during use.")
body("Example 1 - Grammar:")
body('Selected text: "their going to loose the match if they '
     'dont practice"')
body('Action: grammar. AI output: "They\'re going to lose the '
     'match if they don\'t practice." The user reviews the '
     'preview and clicks Replace selection; the change is '
     'saved by autosave.')
body("Example 2 - Tone (professional):")
body('Selected text: "hey, the report is kinda late, can u '
     'send it asap"')
body('Action: tone (professional). AI output: "Hello, the '
     'report is running behind schedule. Could you please '
     'send it as soon as possible?"')
body("Example 3 - Suggestion lifecycle:")
body("An AI suggestion proposes replacing a verbose "
     "sentence. The user opens the Suggestions tab, sees "
     "the original, suggested text, and reason, and accepts "
     "it. The passage is replaced in the editor and the "
     "suggestion status becomes accepted; a second accept "
     "attempt returns a conflict because it is already "
     "resolved.")

h3("Appendix B: Evaluation and Testing Records", numbered=False)
bullets([
    "Backend suite: 202 pytest cases covering auth, "
    "documents, revisions, versions, ACLs, AI actions and "
    "providers, suggestions, sharing, WebSocket, metrics, "
    "analytics, exports, and health.",
    "Frontend suite: 88 Vitest cases covering services, "
    "interceptor, dashboard, editor, AI output, suggestion "
    "list, version history, and app shell.",
    "Production build: clean, initial bundle ~233 kB, lazy "
    "editor bundle ~524 kB.",
    "Evaluation scripts verified against template data; "
    "participant collection pending.",
])

h3("Appendix C: Ethical Compliance and User Privacy", numbered=False)
bullets([
    "The system is a writing assistant, not an autonomous "
    "content generator; all AI output requires explicit "
    "user acceptance.",
    "Metrics record no document content or user "
    "identifiers; frontend collection is opt-in.",
    "All data access is backend-authenticated; Firestore "
    "denies direct client reads/writes; secrets are "
    "gitignored.",
    "Tests use mocked services; no live Firebase data or "
    "AI provider calls are made by the test suite.",
])

h3("Appendix D: Supporting Resources", numbered=False)
bullets([
    "FastAPI - backend framework.",
    "Angular + Angular Material - frontend framework and "
    "UI components.",
    "TipTap / ProseMirror - rich-text editor core.",
    "Firebase Authentication + Cloud Firestore - "
    "identity and storage.",
    "Ollama / OpenAI-compatible APIs - LLM providers.",
    "python-docx and reportlab - DOCX and PDF export.",
    "Locust, textstat, language-tool-python, scipy - "
    "evaluation tooling.",
])
page_break_clean()

h1("References", numbered=False)
refs = [
    "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., "
    "Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention is "
    "All You Need. In Advances in Neural Information Processing "
    "Systems (NeurIPS).\nhttps://arxiv.org/abs/1706.03762",
    "Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2019). "
    "BERT: Pre-training of Deep Bidirectional Transformers for "
    "Language Understanding. In Proceedings of NAACL-HLT.\n"
    "https://arxiv.org/abs/1810.04805",
    "Brown, T., Mann, B., Ryder, N., Subbiah, M., Kaplan, J., "
    "Dhariwal, P., ... & Amodei, D. (2020). Language Models are "
    "Few-Shot Learners. In Advances in Neural Information Processing "
    "Systems (NeurIPS).\nhttps://arxiv.org/abs/2005.14165",
    "Touvron, H., Lavril, T., Izacard, G., Martinet, X., Lachaux, "
    "M. A., Lacroix, T., ... & Lample, G. (2023). LLaMA: Open and "
    "Efficient Foundation Language Models. arXiv preprint "
    "arXiv:2302.13971.\nhttps://arxiv.org/abs/2302.13971",
    "Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). "
    "Design Science in Information Systems Research. MIS Quarterly, "
    "28(1), 75-105.\nhttps://doi.org/10.2307/25148625",
    "Ellis, C. A., & Gibbs, S. J. (1989). Concurrency Control in "
    "Groupware Systems. In Proceedings of ACM SIGMOD.\n"
    "https://doi.org/10.1145/67544.66963",
    "Shapiro, M., Preguica, N., Baquero, C., & Zawirski, M. (2011). "
    "Conflict-free Replicated Data Types. In Proceedings of the 13th "
    "International Symposium on Stabilization, Safety, and Security "
    "of Distributed Systems (SSS).\nhttps://hal.inria.fr/inria-00609399",
    "Brooke, J. (1996). SUS: A Quick and Dirty Usability Scale. In "
    "Usability Evaluation in Industry, Taylor & Francis.\n"
    "https://www.researchgate.net/publication/228593520",
    "Fielding, R. T., & Taylor, R. N. (2002). Principled Design of "
    "the Modern Web Architecture. ACM Transactions on Internet "
    "Technology, 2(2), 115-150.\nhttps://doi.org/10.1145/514183.514185",
    "OpenAI. (2023). Best Practices for Responsible AI and Model "
    "Safety.\nhttps://platform.openai.com/docs/safety-best-practices",
    "FastAPI Documentation. (2024). FastAPI: Modern, Fast "
    "(High-performance) Web Framework for Building APIs with "
    "Python.\nhttps://fastapi.tiangolo.com/",
    "Angular Documentation. (2024). Angular: The Web Development "
    "Framework for Building Modern Applications.\n"
    "https://angular.dev/",
    "TipTap Documentation. (2024). The Headless Editor Framework "
    "Built on ProseMirror.\nhttps://tiptap.dev/",
    "Firebase Documentation. (2024). Firebase Authentication and "
    "Cloud Firestore.\nhttps://firebase.google.com/docs",
    "Ollama Documentation. (2024). Get Up and Running with Large "
    "Language Models Locally.\nhttps://ollama.com/",
]
for ref in refs:
    p = doc.add_paragraph(style="Body Text")
    for j, line in enumerate(ref.split("\n")):
        if j:
            p.add_run().add_break()
        p.add_run(line)
page_break_clean()

h1("Glossary", numbered=False)
glossary = [
    ("LLM (Large Language Model)", "A neural network "
     "trained on large text corpora that can generate and "
     "transform natural language."),
    ("TipTap / ProseMirror", "A headless rich-text editor "
     "framework; document content is stored as structured "
     "JSON."),
    ("Firestore", "Google's serverless NoSQL document "
     "database used for all application data."),
    ("Firebase Authentication", "Identity service that "
     "issues ID tokens verified by the backend on every "
     "request."),
    ("Optimistic Concurrency / CAS", "A write strategy "
     "where updates succeed only if the stored revision "
     "matches the client's expected revision, preventing "
     "silent overwrites."),
    ("Checkpoint / Snapshot", "A saved copy of a "
     "document's state; checkpoints are written "
     "automatically, snapshots manually."),
    ("RBAC (Role-Based Access Control)", "Permission "
     "model assigning owner, editor, or viewer roles to "
     "document collaborators."),
    ("WebSocket", "A persistent bidirectional connection "
     "used for presence, remote cursors, and live update "
     "events."),
    ("CRDT", "Conflict-free Replicated Data Type; a data "
     "structure that allows concurrent edits to merge "
     "automatically."),
    ("OT (Operational Transformation)", "Algorithm for "
     "merging concurrent edits by transforming "
     "operations against each other."),
    ("NDJSON", "Newline-Delimited JSON; a streaming "
     "format where each line is a JSON object, used for "
     "delta/done/error frames."),
    ("SUS (System Usability Scale)", "A standard "
     "10-item questionnaire that produces a 0-100 "
     "usability score."),
    ("Cohen's d", "A standardized effect-size measure "
     "for the difference between two means."),
    ("Flesch-Kincaid", "A readability formula scoring "
     "how easy text is to read."),
    ("Ollama", "A tool for running open-source LLMs "
     "locally."),
    ("DSR (Design Science Research)", "A research "
     "paradigm based on building and evaluating "
     "artifacts."),
]
for term, definition in glossary:
    bold_term_para(term, definition)
page_break_clean()

h1("Checklist of Items for the Final Dissertation / "
   "Project / Project Work Report", numbered=False)
body("This checklist is to be attached as the last page "
     "of the final report and duly completed, verified, "
     "and signed by the student.")
checklist = [
    "Is the final report neatly formatted with all the "
    "elements required for a technical report?",
    "Is the cover page in proper format as given in "
    "Annexure A?",
    "Is the title page (inner cover page) in proper "
    "format?",
    "Is the certificate from the supervisor in proper "
    "format and signed?",
    "Is the abstract included and written within one "
    "page, with keywords?",
    "Is the title of the report adequately descriptive "
    "and precise?",
    "Is the list of abbreviations/acronyms included?",
    "Does the report contain a summary of the "
    "literature survey?",
    "Does the table of contents include page numbers? "
    "Are pages, figures, and tables numbered properly?",
    "Is the conclusion based on discussion of the work?",
    "Are references given and cited properly in the "
    "text?",
    "Is the report format and content according to the "
    "guidelines?",
]
for i, item in enumerate(checklist, 1):
    body(f"{i}. {item}", justify=False)
body("Declaration by Student: I certify that I have "
     "properly verified all the items in this checklist "
     "and ensure that the report is in proper format as "
     "specified in the course handout.")

# ==================================================================
# body section numbering + footers
# ==================================================================
set_pgnum(final_sectPr, "decimal", 1)

# footers: PAGE field renders roman in section 0 (front matter),
# arabic in section 1 (body), per each section's pgNumType.
sections = doc.sections
for idx, section in enumerate(sections):
    section.footer.is_linked_to_previous = False
    fp = section.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_field(fp)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(f"Written: {OUT}")
