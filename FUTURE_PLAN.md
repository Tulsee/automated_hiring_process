# `One important limitation`

If a resume is actually a scanned image:

PDF
│
└── Image of resume

then

page.extract_text() it may return None

Later, your pipeline can become:

Resume
│
┌────────┴────────┐
│ │
Text PDF Scanned PDF
│ │
pypdf OCR
│ │
└────────┬────────┘
▼
Plain Text
