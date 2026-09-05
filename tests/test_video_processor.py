"""Offline integration tests for the local video-to-PDF pipeline."""

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

import video_processor
from video_processor import SimpleVideoProcessor


class VideoProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.video_path = Path(self.temp_dir.name) / "sample.avi"

        writer = cv2.VideoWriter(
            str(self.video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (320, 180)
        )
        self.assertTrue(writer.isOpened(), "OpenCV could not create the synthetic test video")
        for index in range(30):
            # Three colourful, sharp slide-like scenes with overlaid text.
            color = [(30, 40, 220), (40, 180, 50), (220, 80, 30)][index // 10]
            frame = np.full((180, 320, 3), color, dtype=np.uint8)
            cv2.rectangle(frame, (24, 24), (296, 156), (255, 255, 255), 3)
            cv2.putText(
                frame,
                f"Slide {index // 10 + 1}",
                (70, 95),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            writer.write(frame)
        writer.release()

    def test_safe_filename_removes_path_characters(self):
        self.assertEqual(
            SimpleVideoProcessor._safe_filename(" ../my lecture: 01 "), "my_lecture_01"
        )
        self.assertEqual(SimpleVideoProcessor._safe_filename(""), "video_notes")

    def test_extract_frames_and_create_pdf_in_temp_storage(self):
        # OCR is external and not relevant to this deterministic image/PDF test.
        original_ocr_setting = video_processor.OCR_AVAILABLE
        video_processor.OCR_AVAILABLE = False
        self.addCleanup(setattr, video_processor, "OCR_AVAILABLE", original_ocr_setting)

        processor = SimpleVideoProcessor(capture_interval_seconds=0.5, min_sharpness=1)
        frames = processor.extract_best_frames(self.video_path, "../sample lecture")

        self.assertGreaterEqual(len(frames), 3)
        self.assertEqual(processor.stats["total_frames"], 30)
        self.assertTrue(all(Path(frame["file"]).is_file() for frame in frames))
        self.assertTrue(all("ai-video-to-pdf" in Path(frame["file"]).parts for frame in frames))

        pdf_path = processor.create_pdf(frames, "../sample lecture")
        self.assertIsNotNone(pdf_path)
        pdf = Path(pdf_path)
        self.assertTrue(pdf.is_file())
        self.assertEqual(pdf.read_bytes()[:4], b"%PDF")
        self.assertTrue("ai-video-to-pdf" in pdf.parts)

        workspace = processor.workspace_dir
        processor.cleanup()
        self.assertIsNotNone(workspace)
        self.assertFalse(workspace.exists())

    def test_fallback_creates_frames_when_quality_filter_rejects_everything(self):
        original_ocr_setting = video_processor.OCR_AVAILABLE
        video_processor.OCR_AVAILABLE = False
        self.addCleanup(setattr, video_processor, "OCR_AVAILABLE", original_ocr_setting)

        # No frame can meet this threshold, so this exercises the relaxed fallback path.
        processor = SimpleVideoProcessor(capture_interval_seconds=0.5, min_sharpness=10**12)
        frames = processor.extract_best_frames(self.video_path, "fallback")

        self.assertGreaterEqual(len(frames), 3)
        self.assertTrue(all("fallback_" in Path(frame["file"]).name for frame in frames))
        processor.cleanup()

    def test_process_file_to_pdf_accepts_a_local_video(self):
        original_ocr_setting = video_processor.OCR_AVAILABLE
        video_processor.OCR_AVAILABLE = False
        self.addCleanup(setattr, video_processor, "OCR_AVAILABLE", original_ocr_setting)

        processor = SimpleVideoProcessor(capture_interval_seconds=0.5, min_sharpness=1)
        pdf_path = processor.process_file_to_pdf(self.video_path, "local upload")
        self.addCleanup(processor.cleanup)

        self.assertIsNotNone(pdf_path)
        self.assertEqual(Path(pdf_path).read_bytes()[:4], b"%PDF")
        self.assertGreaterEqual(processor.stats["key_frames"], 3)

    def test_process_file_to_pdf_rejects_a_missing_file(self):
        processor = SimpleVideoProcessor()
        self.addCleanup(processor.cleanup)
        self.assertIsNone(processor.process_file_to_pdf("/tmp/does-not-exist.mp4", "notes"))
        self.assertEqual(processor.last_error, "The uploaded video file could not be read.")

    def test_empty_video_url_does_not_start_a_download(self):
        processor = SimpleVideoProcessor()
        self.assertIsNone(processor.download_video("", "notes"))
        self.assertEqual(processor.last_error, "A video URL is required.")
        processor.cleanup()


if __name__ == "__main__":
    unittest.main()
