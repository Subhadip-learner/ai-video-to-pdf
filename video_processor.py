# Import required libraries
import cv2            # OpenCV: used for video processing (reading frames, edge detection, etc.)
import img2pdf        # For converting extracted images into a single PDF
import os             # File and folder handling (create dirs, delete files, etc.)
import glob           # For matching file patterns (not directly used here, but usually for listing files)
import yt_dlp         # To download YouTube videos (replacement of youtube-dl)
import time           # For timing execution (used to calculate processing time)
import numpy as np    # For numerical operations (arrays, histograms, etc.)

# Optional OCR support
try:
    import pytesseract         # OCR library (extracts text from images)
    OCR_AVAILABLE = True       # If pytesseract is available, enable OCR
except Exception:
    OCR_AVAILABLE = False      # If not installed, disable OCR

# -------------------------------
# Main Class: Handles video → frames → PDF
# -------------------------------
class SimpleVideoProcessor:
    def __init__(self,
                 capture_interval_seconds=5,   # Capture 1 frame every 5 seconds by default
                 similarity_threshold=0.90,    # If histogram correlation > 0.9 → frames considered similar
                 replace_sharpness_factor=1.10,# New frame must be at least 10% sharper to replace
                 replace_text_extra=10,        # New frame must contain 10+ more text characters
                 min_sharpness=50):            # Minimum sharpness to consider a frame valid
        """
        Initializes the processor with thresholds for frame selection.
        """
        self.capture_interval_seconds = capture_interval_seconds
        self.similarity_threshold = similarity_threshold
        self.replace_sharpness_factor = replace_sharpness_factor
        self.replace_text_extra = replace_text_extra
        self.min_sharpness = min_sharpness

        # Store statistics for processing summary
        self.processing_stats = {
            'total_frames': 0,     # Total frames in the video
            'key_frames': 0,       # Frames finally saved
            'video_duration': 0    # Duration of video in seconds
        }

    # (utility methods such as _frame_sharpness, _edge_density, _text_amount,
    #  _histogram, _hist_correlation, and _is_new_better go here)
    # Assume they exist above as in your original file.

    # ---------- Step 2: Extract key frames ----------
    def extract_best_frames(self, video_path, output_name):
        """
        Go through video and pick best frames based on sharpness, similarity, and text.
        This method:
          - Opens video
          - Samples frames every capture_interval_seconds
          - Skips blurry frames
          - Uses histogram correlation to detect similarity to last saved
          - Saves distinct frames, and replaces the last saved if a similar-but-better frame appears
        Returns:
          - captured: list of dicts with metadata for each saved frame
        """
        # open the video captured by OpenCV
        cap = cv2.VideoCapture(video_path)
        # if unable to open (bad path, unsupported file) -> bail out
        if not cap.isOpened():
            print("❌ Cannot open video file")
            return None

        # read video properties safely, fallback to sensible defaults
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0  # frames per second
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)  # total frame count
        duration = (total_frames / fps) if fps else 0  # duration in seconds

        # store stats for outside use / reporting
        self.processing_stats['video_duration'] = duration
        self.processing_stats['total_frames'] = total_frames
        # log a short summary
        print(f"🎬 Video Info: {duration:.1f}s, {total_frames} frames, {fps:.1f} FPS")

        # ensure output directory exists (one folder per run)
        output_dir = f"{output_name}_slides"
        os.makedirs(output_dir, exist_ok=True)

        captured = []   # list to hold metadata about saved frames
        last_saved = None  # will hold the last saved frame's info (for comparison)

        # calculate how many frames to skip between samples to achieve the requested seconds interval
        interval_frames = max(1, int(round(self.capture_interval_seconds * fps)))

        # iterate through the video by jumping to every interval frame
        for frame_idx in range(0, total_frames, interval_frames):
            # set the capture position to the current frame index
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            # read the frame
            ret, frame = cap.read()
            # if reading failed (end-of-file, corrupt), skip this position
            if not ret:
                continue

            # compute sharpness (Laplacian variance)
            sharp = self._frame_sharpness(frame)
            # skip frames that are too blurry to be useful
            if sharp < self.min_sharpness:
                continue  # move to next sampled frame

            # compute structural features and optional OCR
            edge = self._edge_density(frame)  # how many edges per pixel
            text_amt, text_content = (0, "")  # defaults if OCR not available
            if OCR_AVAILABLE:
                try:
                    text_amt, text_content = self._text_amount(frame)
                except Exception:
                    text_amt, text_content = (0, "")

            # build a color histogram (HSV) used as a robust similarity metric
            hist = self._histogram(frame)

            # gather all metadata about this sampled frame in a dict
            new_info = {
                'frame': frame,
                'time': frame_idx / fps,         # timestamp in seconds
                'sharpness': sharp,
                'edge_density': edge,
                'text_amount': text_amt,
                'text_content': text_content,
                'hist': hist
            }

            # If this is the very first saved frame, just save it without comparison
            if last_saved is None:
                filename = f"{output_dir}/slide_{len(captured)+1:03d}.png"  # file naming scheme
                cv2.imwrite(filename, frame)  # write the image file
                new_info['file'] = filename
                # append a compact metadata dict to 'captured'
                captured.append({
                    'file': filename,
                    'time': new_info['time'],
                    'sharpness': sharp,
                    'edge_density': edge,
                    'text_amount': text_amt
                })
                last_saved = new_info  # track it for future comparisons
                print(f"📸 Saved (initial) frame at {new_info['time']:.1f}s")
                continue  # move to next sampled frame

            # Compare similarity between the newly sampled frame and the last saved frame
            corr = self._hist_correlation(new_info['hist'], last_saved['hist'])

            # If the new frame is sufficiently different (low correlation), save it as a new slide
            if corr < self.similarity_threshold:
                filename = f"{output_dir}/slide_{len(captured)+1:03d}.png"
                cv2.imwrite(filename, frame)
                new_info['file'] = filename
                captured.append({
                    'file': filename,
                    'time': new_info['time'],
                    'sharpness': sharp,
                    'edge_density': edge,
                    'text_amount': text_amt
                })
                last_saved = new_info  # update last_saved to this newly saved frame
                print(f"📸 Saved distinct frame at {new_info['time']:.1f}s (corr={corr:.3f})")
                continue  # go to next sample

            # If frames are similar (high correlation) we might still replace the last saved if this one is better
            if corr >= self.similarity_threshold:
                # call the decision function that compares sharpness, text amount, and edge density
                if self._is_new_better(new_info, last_saved):
                    try:
                        filename = last_saved.get('file')  # existing filename to overwrite
                        if filename:
                            cv2.imwrite(filename, frame)  # overwrite the image with this better frame
                            # update the metadata of the last captured entry
                            if captured:
                                captured[-1].update({
                                    'time': new_info['time'],
                                    'sharpness': sharp,
                                    'edge_density': edge,
                                    'text_amount': text_amt
                                })
                            new_info['file'] = filename
                            last_saved = new_info  # update last_saved to point to the improved frame
                            print(f"🔁 Replaced with better frame at {new_info['time']:.1f}s")
                    except Exception as e:
                        # if file write fails for any reason, log but continue execution
                        print(f"⚠️ Replacement failed: {e}")
                # if not better, simply skip — no file saved and no updates required
                continue

        # finished sampling -> release the capture resource
        cap.release()

        # If the algorithm found too few captures (e.g., static video, all blurry), run fallback uniform sampling
        if len(captured) < 3:
            print("🔄 Using fallback capture...")
            fallback = self._fallback_capture(video_path, output_dir, total_frames, fps)
            # merge fallback frames, ensuring no duplicates by filename
            for f in fallback:
                if f['file'] not in [c['file'] for c in captured]:
                    captured.append(f)

        # update stats and return the list of captured frames metadata
        self.processing_stats['key_frames'] = len(captured)
        return captured

    # ---------- Fallback capture ----------
    def _fallback_capture(self, cap_or_path, output_dir, total_frames, fps):
        """
        Uniform sampling fallback to ensure that the output contains at least a few frames.
        This method:
          - Samples `num_to_capture` frames evenly across the video
          - Performs the same basic quality checks (sharpness, optional OCR)
          - Returns a list of metadata dicts for files it writes into output_dir
        """
        captured_frames = []  # will contain metadata for fallback images
        must_close = False

        # cap_or_path can be either an already-open cv2.VideoCapture or a file path string
        if isinstance(cap_or_path, str):
            cap = cv2.VideoCapture(cap_or_path)  # open a new capture if we were passed a path
            must_close = True
        else:
            cap = cap_or_path  # reuse provided capture object

        # decide how many fallback frames to capture:
        #   - at most 20
        #   - at least 1
        #   - scaled to video length (total_frames // 100)
        num_to_capture = min(20, max(1, total_frames // 100))

        # uniformly sample positions across the entire video
        for i in range(num_to_capture):
            # pick a frame index proportional to i
            frame_idx = int((i / max(1, num_to_capture)) * total_frames)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue  # skip if unable to read

            # quality checks similar to the main pipeline
            sharp = self._frame_sharpness(frame)
            if sharp < self.min_sharpness:
                continue  # skip very blurry frames

            edge = self._edge_density(frame)
            text_amt, _ = (0, "")
            if OCR_AVAILABLE:
                try:
                    text_amt, _ = self._text_amount(frame)
                except:
                    text_amt = 0

            # write the fallback image file
            filename = f"{output_dir}/slide_fb_{len(captured_frames)+1:03d}.png"
            cv2.imwrite(filename, frame)
            # append metadata dict for this fallback file
            captured_frames.append({
                'file': filename,
                'time': frame_idx / (fps or 1.0),
                'sharpness': sharp,
                'edge_density': edge,
                'text_amount': text_amt
            })

        # if we opened a capture inside this function, close it
        if must_close:
            cap.release()
        return captured_frames

    # ---------- Step 3: Create PDF ----------
    def create_pdf(self, image_files, output_name):
        """
        Take list of images (or list of metadata dicts containing 'file') and convert them
        into a single PDF using img2pdf.
        Returns the path to the PDF file on success, or None on failure.
        """
        # nothing to do if empty input
        if not image_files:
            return None

        # support both formats: list of filenames or list of dicts containing 'file'
        if isinstance(image_files[0], dict):
            files = [d['file'] for d in image_files]
        else:
            files = image_files

        # sort filenames so pages appear in lexical order (slide_001, slide_002, ...)
        files_sorted = sorted(files)
        pdf_filename = f"{output_name}_notes.pdf"  # target PDF filename

        try:
            # open binary file and write pdf bytes produced by img2pdf
            with open(pdf_filename, "wb") as f:
                f.write(img2pdf.convert(files_sorted))
            print(f"✅ PDF created: {pdf_filename}")
            return pdf_filename
        except Exception as e:
            # log failure and return None to signal the error
            print(f"❌ PDF creation error: {e}")
            return None

    # ---------- Step 4: Main pipeline ----------
    def process_video_to_pdf(self, video_url, content_name):
        """
        High-level wrapper that:
          1. Downloads the video from the URL
          2. Extracts the best frames
          3. Creates a PDF from those frames
          4. Cleans up the downloaded video file
        Returns the created PDF path, or None on failure.
        """
        print("🚀 Starting video processing...")
        start_time = time.time()  # start timing to report runtime later

        # Step 1: download video with yt_dlp
        video_file = self.download_video(video_url, content_name)
        if not video_file:
            return None  # download failed -> abort

        # Step 2: extract best frames from the downloaded video
        frames_info = self.extract_best_frames(video_file, content_name)
        if not frames_info:
            return None  # extraction failed or returned no frames

        # Step 3: create PDF from extracted frame files
        pdf_file = self.create_pdf(frames_info, content_name)

        # Cleanup: remove downloaded video file to save disk space
        try:
            if os.path.exists(video_file):
                os.remove(video_file)
                print(f"🧹 Cleaned up: {video_file}")
        except:
            # if cleanup fails, we ignore it (not critical)
            pass

        # log processing time and return the pdf path
        processing_time = time.time() - start_time
        print(f"⏱️ Total processing time: {processing_time:.1f} seconds")
        return pdf_file