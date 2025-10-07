# 🧠 AI Video to PDF Converter — README



## ❓ Core Problem & Solution (The "Why")

**The Problem**  
Students and professionals often need quick, searchable notes from lecture/tutorial videos.  
Manually screenshotting and organizing frames is **slow, repetitive, and error-prone**.  

**The Solution**  
This project automates the process:  
- ⏬ Download videos (YouTube and others) using `yt_dlp`.  
- 🖼 Extract **key frames/slides** intelligently (sharpness, uniqueness, text content).  
- 🔄 Replace poor frames with higher-quality ones dynamically.  
- 🔍 (Optional) OCR to capture text for **searchable PDFs**.  
- 📑 Export to a clean, single PDF ready for study or sharing. 

## 📌 Overview

This project provides an **AI-powered system** to automatically convert educational YouTube videos into **clean, organized PDF notes** by intelligently extracting key frames (e.g., slides, diagrams, text-heavy visuals) and compiling them into a downloadable PDF. The system leverages **OpenCV for frame analysis**, **yt-dlp for video downloading**, **pytesseract for OCR**, and **img2pdf for PDF generation**, all wrapped in a beautiful **Streamlit web UI**.

The core logic is split across two main files:

- `video_processor.py`: Handles video downloading, frame extraction, filtering, and PDF creation.
- `streamlit_app.py`: Provides a user-friendly web interface for input, processing, and download.

---

## 🛠️ How It Works (Code Analysis)

### 1. **Video Processing Pipeline (`video_processor.py`)**

#### Class: `SimpleVideoProcessor`

This class encapsulates the entire logic for converting a video into a PDF of key frames.

##### 📥 Initialization (`__init__`)
- Accepts configurable thresholds:
  - `capture_interval_seconds`: How often (in seconds) to sample frames.
  - `similarity_threshold`: Histogram correlation threshold to detect duplicate/similar frames.
  - `replace_sharpness_factor`: Minimum sharpness improvement to replace a similar frame.
  - `replace_text_extra`: Minimum additional text characters to consider a frame better.
  - `min_sharpness`: Minimum Laplacian variance to consider a frame non-blurry.

- Initializes `processing_stats` to track video duration, total frames, and key frames extracted.

##### 🔍 Utility Methods (Not Shown, But Assumed)
The class relies on the following internal helper methods (not shown in your code snippet but referenced):
- `_frame_sharpness(frame)`: Computes Laplacian variance to measure sharpness.
- `_edge_density(frame)`: Measures structural complexity (edges per pixel).
- `_text_amount(frame)`: Uses `pytesseract` to extract and count text characters.
- `_histogram(frame)`: Converts frame to HSV and computes a normalized color histogram.
- `_hist_correlation(hist1, hist2)`: Computes histogram correlation (0–1) for similarity.
- `_is_new_better(new_info, last_saved)`: Compares sharpness, edge density, and text to decide if a new frame should replace a similar one.

##### 🖼️ Frame Extraction (`extract_best_frames`)
1. **Video Metadata Extraction**: Uses OpenCV to get FPS, total frames, and duration.
2. **Interval Sampling**: Jumps every `capture_interval_seconds * FPS` frames.
3. **Quality Filtering**:
   - Skips blurry frames (`sharpness < min_sharpness`).
   - Computes edge density and text content (if OCR is available).
4. **Similarity Detection**:
   - Compares histograms of current and last saved frame.
   - If similarity < threshold → saves as new slide.
   - If similarity ≥ threshold → checks if it's a better version (sharper, more text) and replaces if so.
5. **Fallback Capture**:
   - If fewer than 3 frames are captured, falls back to uniform sampling across the video.

##### 📄 PDF Creation (`create_pdf`)
- Accepts a list of image file paths or metadata dicts.
- Sorts files lexicographically (e.g., `slide_001.png`, `slide_002.png`).
- Uses `img2pdf` to generate a single PDF.

##### 🚀 End-to-End Pipeline (`process_video_to_pdf`)
1. Downloads video using `yt_dlp`.
2. Extracts best frames using `extract_best_frames`.
3. Creates PDF using `create_pdf`.
4. Cleans up the downloaded video file.

---

### 2. **Web Interface (`streamlit_app.py`)**

#### 🎨 UI Components
- **Page Configuration**: Sets title, icon, layout, and sidebar state.
- **Custom CSS**: Adds styling for headers, cards, status boxes, and input sections.
- **Form Input**: Collects:
  - YouTube URL
  - Content name (for PDF filename)
  - Video quality (1080p–360p)
  - Optional training PDF (currently unused in backend)

#### 🔄 Processing Flow
1. **Input Validation**: Ensures URL is provided and contains YouTube domain.
2. **Status Updates**: Shows animated step-by-step progress (e.g., downloading, extracting, PDF creation).
3. **Error Handling**: Catches and displays exceptions in the UI.
4. **Results Display**:
   - Shows processing metrics (slides extracted, duration, etc.)
   - Provides a **download button** for the generated PDF.
   - Triggers **balloons animation** on success.

#### 🧠 AI Features Highlighted
- **Smart Frame Selection**: Avoids duplicates using histogram correlation.
- **Quality-Aware Replacement**: Prefers sharper, text-rich frames.
- **OCR Integration**: Prioritizes frames with educational text.
- **Fallback Strategy**: Ensures output even for static or blurry videos.

---

## 📦 Dependencies

### Python Libraries
- `opencv-python` – Video frame processing and analysis.
- `img2pdf` – Converts images to PDF.
- `yt-dlp` – Downloads YouTube videos.
- `pytesseract` *(optional)* – OCR for text detection.
- `numpy` – Numerical operations (histograms, arrays).
- `streamlit` – Web UI framework.

### System Dependencies
- **Tesseract OCR** (if using OCR):
  - Install via:  
    - **Windows**: [Tesseract installer](https://github.com/UB-Mannheim/tesseract/wiki)  
    - **macOS**: `brew install tesseract`  
    - **Linux**: `sudo apt install tesseract-ocr`

---
## 📁 Project Structure
```
video-to-pdf-app/
│
├── streamlit_app.py          # Main Streamlit UI
├── video_processor.py        # Core processing logic
│
├── requirements.txt          # Python dependencies
├── README.md                 # Project overview & usage instructions
├── LICENSE                   # MIT License (optional but recommended)
└── .gitignore                # Ignore venv, cache, etc.
```



## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Subhadip-learner/ai-video-to-pdf.git
cd ai-video-to-pdf
```

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

> **Note**: If `requirements.txt` is missing, create one with:
```txt
opencv-python
img2pdf
yt-dlp
pytesseract
numpy
streamlit
```

### 4. Install Tesseract OCR (Optional but Recommended)
Follow system-specific instructions above.

### 5. Run the App
```bash
streamlit run streamlit_app.py
```

---

## 🧪 Usage

1. Open the app in your browser (usually `http://localhost:8501`).
2. Enter a **YouTube URL** (e.g., lecture, tutorial).
3. Provide a **Content Name** (e.g., `Neural_Networks_Lecture`).
4. Select desired **Video Quality**.
5. Click **"Start Intelligent Processing"**.
6. Wait for processing to complete.
7. Download the generated PDF.

---

## 🧩 Example Workflow

**Input**:  
- URL: `https://www.youtube.com/watch?v=abc123`  
- Content Name: `ML_Lecture_1`

**Processing Steps**:
1. Downloads `ML_Lecture_1.mp4` (~720p).
2. Samples frames every 5 seconds.
3. Filters blurry frames (sharpness < 50).
4. Detects slide changes using histogram correlation.
5. Replaces similar frames if sharper or more text-rich.
6. Falls back to uniform sampling if <3 frames found.
7. Generates `ML_Lecture_1_notes.pdf`.

**Output**:  
- Clean PDF with key educational slides.
- Processing report with metrics.

## ⚠️ Limitations & Notes

- **YouTube Only**: Currently supports only public YouTube videos.
- **OCR Optional**: Without `pytesseract`, text-aware filtering is disabled.
- **Processing Time**: Longer videos = more time (e.g., 1-hour video ≈ 2–5 mins).
- **Frame Quality**: Works best with clear, static slides (not dynamic animations).
- **Training PDF**: The UI allows uploading a training PDF, but backend doesn't use it yet (future enhancement).

---

## 🧠 Future Enhancements

- ✅ **Semantic Frame Selection**: Use CLIP or ViT to understand slide content.
- ✅ **Text Summarization**: Extract and summarize slide text into notes.
- ✅ **Multi-Language OCR**: Support non-English content.
- ✅ **Cloud Processing**: Offload to AWS/GCP for large videos.
- ✅ **Training PDF Integration**: Use uploaded PDF to guide frame selection.
- ✅ **Train or use a pre-trained Convolutional Neural Network (CNN) or Vision Transformer (ViT) to classify frames as**: Slide / Key-Frame Detection (CNN / ViT)

          📊 Slide (with text/diagrams)

          👨‍🏫 Instructor only

         📹 Transition/blank frames

    Keep only slide frames → improves PDF clarity.
---

## 📄 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)  
###  © 2025 Subhadip Medya 

---

## 🙌 Acknowledgements

This project was made possible thanks to the support, tools, and open-source contributions of the community. Special thanks to:

- **Python** – for being the backbone of the project.
          https://www.youtube.com/live/1z5-O7-5AXk?si=UbcTHZ9rH99-_saE
- **OpenCV** – for powerful video processing and frame extraction.
         https://youtu.be/yQu_3e7MAr0
- **yt-dlp** – for making video downloads seamless. 
         
- **img2pdf** – for converting extracted frames into high-quality PDFs.
         https://github.com/josch/img2pdf
- **Streamlit** – for enabling an intuitive and interactive web interface.
         [https://www.youtube.com/watch?v=ij5Ol925gwQ&list=PLgkF0qak9G4-TC9_tKW1V4GRcJ9cdmnlx]()
- **Open-source contributors & the developer community** – whose shared knowledge inspired this work.

---

## 📞 Contact

Have questions? Want to collaborate?

- 📧 **Email**: subhadipmedya2512@gmail.com
- 🌐 **GitHub**: [Subhadip-learner](https://github.com/Subhadip-learner)
- 💬 **Thread**: [@qubits_subhadipxagi](https://www.threads.com/@qubits_subhadipxagi)

Let’s grow smarter agriculture together! 🌱

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repo.
2. Create your feature branch (`git checkout -b feature/new-model`).
3. Commit your changes (`git commit -m 'Add new feature'`).
4. Push to the branch (`git push origin feature/new-model`).
5. Open a pull request.

Please ensure:
- Code follows PEP8 standards.
- Add comments where needed.
- Update `README.md` if applicable.

---

## 🎉 Ready to Deploy?

Just run `streamlit_app.py` and it will take you to the website. 
Happy coding! 🚀# ai-video-to-pdf
