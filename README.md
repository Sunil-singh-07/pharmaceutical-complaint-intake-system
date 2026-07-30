# 💊 Pharmaceutical Complaint Intake System

An AI-powered Pharmaceutical Complaint Intake System that automates the processing of pharmaceutical product complaints using **React**, **FastAPI**, and **LangGraph**. The application extracts structured information from user input or uploaded PDF documents, validates the extracted data, performs AI-powered risk assessment, and generates actionable recommendations.

---

## 🚀 Features

### 📄 Complaint Submission
- Submit complaints using text input.
- Upload pharmaceutical complaint documents in PDF format.
- Automatic PDF text extraction.

### 🤖 AI-Powered Information Extraction
- Extracts:
  - Company Name
  - Manufacturer
  - Product Name
  - Generic Name
  - Strength
  - Dosage Form
  - Pack Size
  - Batch Number
  - Manufacturing Date
  - Expiry Date
  - Quantity
  - Complaint Description
  - Complaint Category
  - Complaint Type
  - Defect Type
  - Reported Event
  - Severity
  - Symptoms

### ✅ Validation
- Detects missing mandatory fields.
- Generates validation errors and warnings.
- Helps improve complaint completeness.

### ⚠️ Risk Assessment
- Calculates Risk Score.
- Assigns Risk Priority.
- Identifies Risk Factors.
- Generates Recommended Actions.

### 🧠 AI Summary
- Produces a concise summary of the complaint.
- Enables faster review by Quality Assurance teams.

---

# 🏗️ System Architecture

```
React Frontend
        │
        ▼
 FastAPI Backend
        │
        ▼
PDF Text Extraction
        │
        ▼
 LangGraph Workflow
        │
 ├── Information Extraction
 ├── Validation
 ├── Risk Assessment
 └── AI Summary
        │
        ▼
 Structured JSON Response
        │
        ▼
 React Dashboard
```

---

# 🛠️ Tech Stack

## Frontend
- React
- TypeScript
- Vite

## Backend
- FastAPI
- Python
- SQLAlchemy

## AI
- LangGraph
- LLM-based Information Extraction

---

# 📂 Project Structure

```
pharmaceutical-complaint-intake-system
│
├── backend
│   ├── app
│   ├── tests
│   ├── requirements.txt
│   └── README.md
│
├── frontend
│   ├── src
│   ├── public
│   ├── package.json
│   └── README.md
│
└── README.md
```

---

# ⚙️ Installation

## 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/pharmaceutical-complaint-intake-system.git

cd pharmaceutical-complaint-intake-system
```

---

## 2. Backend Setup

```bash
cd backend

python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file inside the backend folder using `.env.example` as a reference.

Start the backend:

```bash
uvicorn app.main:app --reload
```

Backend runs on:

```
http://localhost:8000
```

---

## 3. Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

Frontend runs on:

```
http://localhost:5173
```

---

# 🔄 End-to-End Workflow

1. User enters complaint text or uploads a PDF.
2. The frontend sends the request to the FastAPI backend.
3. The backend extracts text from the uploaded PDF.
4. The complaint is processed by the LangGraph workflow.
5. AI extracts structured complaint information.
6. Validation checks required fields.
7. Risk assessment calculates priority and score.
8. AI generates a complaint summary.
9. The backend returns structured JSON.
10. The frontend displays the extracted complaint details, AI summary, validation results, and risk assessment.

---

# 📊 Key Functionalities

- PDF Upload
- PDF Text Extraction
- AI Information Extraction
- Complaint Validation
- AI Summary Generation
- Risk Assessment
- Risk Score Calculation
- Recommended Actions
- Session Management

---

# 📷 Screenshots

You can add screenshots of:

- Dashboard
- Complaint Extraction
- AI Summary
- Validation Results
- Risk Assessment

---

# 👨‍💻 Author

**Sunil Singh**

B.Tech Student

Python | AI | Machine Learning | React | FastAPI

---

# 📄 License

This project was developed for educational and internship evaluation purposes.
