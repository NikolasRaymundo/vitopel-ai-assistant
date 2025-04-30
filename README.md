# 🧠 Vitopel AI Assistant

An AI-powered assistant for industrial operations, designed to provide fast, accurate answers to maintenance and production questions — using only trusted internal documentation.

This is a real-world project I'm leading at **Vitopel**, a BOPP film manufacturer, where operators and technicians often struggle to find key information in thousands of scattered documents.

---

## 🚧 Problem We're Solving

Vitopel’s plant runs complex machinery (e.g. Bruckner lines, slitters, chillers). Over time, we’ve accumulated thousands of documents:
- Maintenance manuals
- Quality control logs
- SOPs
- Excel reports
- Scanned troubleshooting forms

When a line breaks at 3am, operators don’t have time to dig through this. That’s where this assistant comes in.

---

## 🧩 How It Works

The assistant:
- Ingests technical documents of any type (PDF, Excel, Word, scanned images)
- Extracts clean, searchable text (including OCR)
- Classifies and chunks content using GPT-4
- Stores it in a semantic vector database
- Lets users ask questions in natural language (English or Portuguese)
- Responds with **only** answers explicitly found in the documents, with:
  - Page numbers
  - Document name
  - Confidence level
  - Visual fallback notices if diagrams are needed

---

## ⚙️ Technologies Used

| Component      | Tools / Libraries                      |
|----------------|-----------------------------------------|
| **Ingestion**  | `pymupdf`, `pytesseract`, `python-docx`, `pandas` |
| **Classification** | `openai` GPT-4 API                    |
| **Vector Search**  | `llama-index` + `chromadb`            |
| **Backend**    | `FastAPI`                               |
| **Frontend**   | `Streamlit` (MVP), planned React + PDF.js |
| **OCR**        | `Tesseract`                             |

---

## ✅ Status

- [x] Project architecture fully defined
- [x] Manual ingestion + classification tested
- [x] MVP assistant built for Bruckner Line 5 manual
- [ ] Full ingestion pipeline in progress
- [ ] Vector database integration under development
- [ ] Web UI being expanded for operators

---

## 📍 Roadmap (Next Steps)

- [ ] Build continuous ingestion pipeline
- [ ] Deploy Chroma-based retrieval backend
- [ ] Expand role-specific response logic
- [ ] Connect to SharePoint document source
- [ ] Enable PDF preview in UI
- [ ] Train plant team to use the tool

---

## 👋 Who Am I?

I'm [**Nikolas Raymundo**](https://www.linkedin.com/in/nikolas-cavalcante-raymundo/), a chemical engineer with field experience at Baker Hughes and current project lead at Vitopel. I’m pivoting into AI-powered operational systems, and this is the first of many.

This project reflects:
- Real industrial complexity
- Actual operational needs
- Production-level engineering mindset

---

## 🧠 Why This Matters (especially to TRACTIAN)

➡️ Turn raw data into real-time, actionable insights.

Let’s build together.