"""Utilities for downloading a public video, selecting useful frames, and creating a PDF.

All generated files are stored in a unique directory below the operating system temporary
directory.  This makes the processor safe to use on serverless hosts such as Vercel, where
the deployed application directory is read-only and only ``/tmp`` can be written to.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Union

import cv2
import img2pdf
import numpy as np
import yt_dlp

try:
    import pytesseract

    OCR_AVAILABLE = True
except Exception:
    # Importing pytesseract is optional.  The rest of the pipeline continues without OCR.
    pytesseract = None
    OCR_AVAILABLE = False


ImageInfo = dict[str, Any]
PathLike = Union[str, Path]


class SimpleVideoProcessor:
    """Convert a public video URL into a PDF containing distinct, useful frames.

    A processor instance is intended for one conversion job.  It creates an isolated
    temporary workspace when processing begins.  Call :meth:`cleanup` after the caller no
    longer needs the generated PDF; the Streamlit UI deliberately retains it long enough for
    the user to download it.
    """

    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".mpeg", ".mpg"}

    def __init__(
        self,
        capture_interval_seconds: float = 5,
        similarity_threshold: float = 0.90,
        replace_sharpness_factor: float = 1.10,
        replace_text_extra: int = 10,
        min_sharpness: float = 50,
    ) -> None:
        self.capture_interval_seconds = max(0.25, float(capture_interval_seconds))
        self.similarity_threshold = float(similarity_threshold)
        self.replace_sharpness_factor = max(1.0, float(replace_sharpness_factor))
        self.replace_text_extra = max(0, int(replace_text_extra))
        self.min_sharpness = max(0.0, float(min_sharpness))

        self.processing_stats = {
            "total_frames": 0,
            "key_frames": 0,
            "video_duration": 0.0,
        }
        self.workspace_dir: Optional[Path] = None
        self.last_error: Optional[str] = None

    @property
    def stats(self) -> dict[str, Union[int, float]]:
        """Backward-compatible name used by the Streamlit interface."""
        return self.processing_stats

    # ---------- Workspace and filename helpers ----------
    @staticmethod
    def _safe_filename(value: str, default: str = "video_notes") -> str:
        """Return a portable filename stem, never a user-controlled path."""
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
        cleaned = cleaned.strip("._-")[:80]
        return cleaned or default

    def _create_workspace(self) -> Path:
        """Create (once) the writable temporary directory for this job."""
        if self.workspace_dir is None:
            base_dir = Path(tempfile.gettempdir()) / "ai-video-to-pdf"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.workspace_dir = Path(tempfile.mkdtemp(prefix="job-", dir=base_dir))
        return self.workspace_dir

    def cleanup(self) -> None:
        """Remove all temporary files belonging to this conversion job."""
        if self.workspace_dir and self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir, ignore_errors=True)
        self.workspace_dir = None

    def _slides_directory(self, output_name: str) -> Path:
        directory = self._create_workspace() / f"{self._safe_filename(output_name)}_slides"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    # ---------- Frame-quality helpers ----------
    @staticmethod
    def _frame_sharpness(frame: np.ndarray) -> float:
        """Measure focus using the variance of the Laplacian (higher is sharper)."""
        if frame is None or frame.size == 0:
            return 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def _edge_density(frame: np.ndarray) -> float:
        """Return the fraction of pixels that are strong Canny edges."""
        if frame is None or frame.size == 0:
            return 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        return float(np.count_nonzero(edges)) / float(edges.size or 1)

    @staticmethod
    def _histogram(frame: np.ndarray) -> np.ndarray:
        """Build a normalized HSV histogram for visual similarity comparison."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        histogram = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
        return cv2.normalize(histogram, histogram).flatten()

    @staticmethod
    def _hist_correlation(hist1: np.ndarray, hist2: np.ndarray) -> float:
        """Return OpenCV histogram correlation, where 1.0 means identical."""
        if hist1 is None or hist2 is None:
            return -1.0
        return float(cv2.compareHist(hist1.astype("float32"), hist2.astype("float32"), cv2.HISTCMP_CORREL))

    @staticmethod
    def _text_amount(frame: np.ndarray) -> tuple[int, str]:
        """OCR a frame and return its non-whitespace character count and text.

        pytesseract can be importable while the system Tesseract binary is missing.  In that
        case its exception is caught by the caller and OCR simply contributes no score.
        """
        if not OCR_AVAILABLE or pytesseract is None:
            return 0, ""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray, config="--psm 6")
        normalized_text = " ".join(text.split())
        return len(re.sub(r"\s+", "", normalized_text)), normalized_text

    def _is_new_better(self, new_info: ImageInfo, previous_info: ImageInfo) -> bool:
        """Decide whether a visually similar frame improves the already saved frame."""
        old_sharpness = max(float(previous_info.get("sharpness", 0.0)), 1.0)
        new_sharpness = float(new_info.get("sharpness", 0.0))
        old_text = int(previous_info.get("text_amount", 0))
        new_text = int(new_info.get("text_amount", 0))
        old_edges = max(float(previous_info.get("edge_density", 0.0)), 1e-6)
        new_edges = float(new_info.get("edge_density", 0.0))

        noticeably_sharper = new_sharpness >= old_sharpness * self.replace_sharpness_factor
        substantially_more_text = new_text >= old_text + self.replace_text_extra
        clearer_structure = (
            new_edges >= old_edges * 1.20 and new_sharpness >= old_sharpness * 0.95
        )
        return noticeably_sharper or substantially_more_text or clearer_structure

    # ---------- Download ----------
    @staticmethod
    def _quality_height(quality: Optional[str]) -> int:
        match = re.search(r"(\d+)", quality or "")
        return int(match.group(1)) if match else 720

    def download_video(self, video_url: str, content_name: str, quality: str = "720p") -> Optional[str]:
        """Download one public video into this job's temporary workspace.

        ``content_name`` is retained in the signature for compatibility.  Downloaded source
        filenames are intentionally fixed and are never built from user input.
        """
        if not video_url or not video_url.strip():
            self.last_error = "A video URL is required."
            return None

        workspace = self._create_workspace()
        max_height = self._quality_height(quality)
        output_template = str(workspace / "source.%(ext)s")
        format_selector = (
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        )
        options = {
            "format": format_selector,
            "outtmpl": output_template,
            "noplaylist": True,
            "merge_output_format": "mp4",
            "restrictfilenames": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 2,
            "fragment_retries": 2,
            # Hosted servers (Vercel, etc.) share datacenter IPs that YouTube's
            # web player often flags as bots.  The mobile player clients are
            # far less aggressive about that check, so prefer them.
            "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
        }

        # Optional backup for strict bot checks: paste a Netscape-format
        # cookies.txt export into the YTDLP_COOKIES environment variable and
        # yt-dlp will authenticate with it.  Never commit cookies to git.
        cookie_data = os.environ.get("YTDLP_COOKIES", "").strip()
        if cookie_data:
            cookie_file = workspace / "cookies.txt"
            cookie_file.write_text(cookie_data)
            options["cookiefile"] = str(cookie_file)

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.extract_info(video_url.strip(), download=True)
        except Exception as error:
            self.last_error = f"Video download failed: {error}"
            print(f"❌ {self.last_error}")
            return None

        candidates = [
            path
            for path in workspace.iterdir()
            if path.is_file() and path.suffix.lower() in self.VIDEO_EXTENSIONS
        ]
        if not candidates:
            self.last_error = "The video was downloaded but no supported video file was produced."
            print(f"❌ {self.last_error}")
            return None

        video_file = max(candidates, key=lambda path: path.stat().st_mtime)
        print(f"✅ Downloaded video: {video_file.name}")
        return str(video_file)

    # ---------- Frame extraction ----------
    def _frame_info(self, frame: np.ndarray, frame_index: int, fps: float) -> ImageInfo:
        sharpness = self._frame_sharpness(frame)
        edge_density = self._edge_density(frame)
        text_amount, text_content = 0, ""
        if OCR_AVAILABLE:
            try:
                text_amount, text_content = self._text_amount(frame)
            except Exception as error:
                # Tesseract is optional, so OCR errors cannot stop PDF generation.
                print(f"⚠️ OCR skipped: {error}")

        return {
            "frame": frame,
            "time": frame_index / (fps or 1.0),
            "sharpness": sharpness,
            "edge_density": edge_density,
            "text_amount": text_amount,
            "text_content": text_content,
            "hist": self._histogram(frame),
        }

    @staticmethod
    def _save_frame(output_dir: Path, frame: np.ndarray, position: int, fallback: bool = False) -> str:
        prefix = "fallback" if fallback else "slide"
        destination = output_dir / f"{prefix}_{position:03d}.png"
        if not cv2.imwrite(str(destination), frame):
            raise OSError(f"Could not write extracted frame: {destination}")
        return str(destination)

    def extract_best_frames(self, video_path: PathLike, output_name: str) -> list[ImageInfo]:
        """Sample a video and save distinct, sufficiently sharp frames.

        When fewer than three frames are selected, uniform fallback sampling is used.  The
        fallback keeps usable frames even when the source is uniformly blurry, so a valid
        video still produces a PDF rather than failing silently.
        """
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError("Cannot open the downloaded video file.")

        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total_frames <= 0:
                raise ValueError("The video contains no readable frames.")

            duration = total_frames / fps
            self.processing_stats.update(
                {
                    "total_frames": total_frames,
                    "video_duration": duration,
                    "key_frames": 0,
                }
            )
            print(f"🎬 Video info: {duration:.1f}s, {total_frames} frames, {fps:.1f} FPS")

            output_dir = self._slides_directory(output_name)
            interval_frames = max(1, int(round(self.capture_interval_seconds * fps)))
            captured: list[ImageInfo] = []
            last_saved: Optional[ImageInfo] = None

            for frame_index in range(0, total_frames, interval_frames):
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = capture.read()
                if not success or frame is None:
                    continue

                info = self._frame_info(frame, frame_index, fps)
                if info["sharpness"] < self.min_sharpness:
                    continue

                if last_saved is None:
                    info["file"] = self._save_frame(output_dir, frame, len(captured) + 1)
                    captured.append(info)
                    last_saved = info
                    print(f"📸 Saved initial frame at {info['time']:.1f}s")
                    continue

                correlation = self._hist_correlation(info["hist"], last_saved["hist"])
                if correlation < self.similarity_threshold:
                    info["file"] = self._save_frame(output_dir, frame, len(captured) + 1)
                    captured.append(info)
                    last_saved = info
                    print(f"📸 Saved distinct frame at {info['time']:.1f}s (corr={correlation:.3f})")
                elif self._is_new_better(info, last_saved):
                    filename = str(last_saved["file"])
                    if not cv2.imwrite(filename, frame):
                        raise OSError(f"Could not replace extracted frame: {filename}")
                    info["file"] = filename
                    captured[-1] = info
                    last_saved = info
                    print(f"🔁 Replaced with a better frame at {info['time']:.1f}s")

            # A target of three makes short/static videos more useful while respecting very
            # small files that physically contain fewer frames.
            target_count = min(3, total_frames)
            if len(captured) < target_count:
                print("🔄 Using fallback frame capture...")
                fallback = self._fallback_capture(
                    str(video_path),
                    output_dir,
                    total_frames,
                    fps,
                    count_needed=target_count - len(captured),
                    existing_times=[float(item["time"]) for item in captured],
                )
                captured.extend(fallback)

            captured.sort(key=lambda item: float(item["time"]))
            self.processing_stats["key_frames"] = len(captured)
            return captured
        finally:
            capture.release()

    def _fallback_capture(
        self,
        cap_or_path: Union[PathLike, cv2.VideoCapture],
        output_dir: PathLike,
        total_frames: int,
        fps: float,
        count_needed: int = 3,
        existing_times: Optional[Iterable[float]] = None,
    ) -> list[ImageInfo]:
        """Uniformly select frames when normal slide detection found too few.

        Quality filtering is deliberately relaxed here.  A non-empty PDF is more helpful
        than rejecting a valid but low-detail video altogether.
        """
        output_path = Path(output_dir)
        must_close = isinstance(cap_or_path, (str, Path))
        capture = cv2.VideoCapture(str(cap_or_path)) if must_close else cap_or_path
        if not capture.isOpened() or total_frames <= 0 or count_needed <= 0:
            if must_close:
                capture.release()
            return []

        try:
            # Oversample slightly; this helps if a selected position cannot be decoded.
            sample_count = min(total_frames, max(count_needed * 3, 3))
            positions = np.linspace(0, total_frames - 1, num=sample_count, dtype=int)
            seen_positions: set[int] = set()
            candidates: list[ImageInfo] = []

            for frame_index in positions.tolist():
                if frame_index in seen_positions:
                    continue
                seen_positions.add(frame_index)
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                success, frame = capture.read()
                if not success or frame is None:
                    continue
                candidates.append(self._frame_info(frame, frame_index, fps))

            if not candidates:
                return []

            known_times = list(existing_times or [])
            # Prefer frames that pass the normal sharpness threshold, but include lower-score
            # frames if that is all a valid video has.
            candidates.sort(key=lambda item: float(item["sharpness"]), reverse=True)
            selected: list[ImageInfo] = []
            for info in candidates:
                if len(selected) >= count_needed:
                    break
                timestamp = float(info["time"])
                # Avoid an exact duplicate of a frame already selected by the main pass.
                if any(abs(timestamp - prior) < 0.01 for prior in known_times):
                    continue
                selected.append(info)
                known_times.append(timestamp)

            # If every uniform position overlapped with main-pass positions, retain the best
            # candidates anyway rather than returning an empty fallback.
            if not selected:
                selected = candidates[:count_needed]

            saved: list[ImageInfo] = []
            for index, info in enumerate(selected, start=1):
                info["file"] = self._save_frame(output_path, info["frame"], index, fallback=True)
                saved.append(info)
            return saved
        finally:
            if must_close:
                capture.release()

    # ---------- PDF generation ----------
    def create_pdf(self, image_files: Union[list[ImageInfo], list[PathLike]], output_name: str) -> Optional[str]:
        """Create a PDF from saved frame metadata or a list of image file paths."""
        if not image_files:
            return None

        if isinstance(image_files[0], dict):
            ordered_images = sorted(image_files, key=lambda item: float(item.get("time", 0.0)))
            files = [str(item["file"]) for item in ordered_images if item.get("file")]
        else:
            files = sorted(str(path) for path in image_files)

        files = [file for file in files if Path(file).is_file()]
        if not files:
            return None

        pdf_path = self._create_workspace() / f"{self._safe_filename(output_name)}_notes.pdf"
        try:
            with pdf_path.open("wb") as pdf_file:
                pdf_file.write(img2pdf.convert(files))
            print(f"✅ PDF created: {pdf_path}")
            return str(pdf_path)
        except Exception as error:
            self.last_error = f"PDF creation failed: {error}"
            print(f"❌ {self.last_error}")
            return None

    # ---------- Main pipeline ----------
    def _build_pdf_from_file(self, video_file: PathLike, content_name: str) -> Optional[str]:
        """Extract frames from a local video file and build the PDF."""
        frames_info = self.extract_best_frames(video_file, content_name)
        if not frames_info:
            self.last_error = "No readable frames could be extracted from the video."
            return None
        return self.create_pdf(frames_info, content_name)

    def process_video_to_pdf(self, video_url: str, content_name: str, quality: str = "720p") -> Optional[str]:
        """Download a video, extract frames, create a PDF, and remove the source video."""
        print("🚀 Starting video processing...")
        start_time = time.time()
        self.last_error = None
        self.processing_stats.update({"total_frames": 0, "key_frames": 0, "video_duration": 0.0})
        self._create_workspace()

        video_file = self.download_video(video_url, content_name, quality)
        if not video_file:
            return None

        try:
            return self._build_pdf_from_file(video_file, content_name)
        finally:
            # The input video is typically much larger than the result and is no longer needed.
            try:
                Path(video_file).unlink(missing_ok=True)
            except OSError:
                pass
            print(f"⏱️ Total processing time: {time.time() - start_time:.1f} seconds")

    def process_file_to_pdf(self, local_path: PathLike, content_name: str) -> Optional[str]:
        """Build a PDF from an already-downloaded video file (e.g. a user upload).

        This path never touches YouTube, so it works even when the hosting
        provider's IP range is blocked by the video site's bot checks.
        """
        print("🚀 Starting video processing...")
        start_time = time.time()
        self.last_error = None
        self.processing_stats.update({"total_frames": 0, "key_frames": 0, "video_duration": 0.0})
        self._create_workspace()

        source = Path(str(local_path))
        if not source.is_file():
            self.last_error = "The uploaded video file could not be read."
            return None

        try:
            return self._build_pdf_from_file(source, content_name)
        finally:
            print(f"⏱️ Total processing time: {time.time() - start_time:.1f} seconds")
