import re
import time
import cv2
import easyocr
import numpy as np
from app.schemas import PlateCandidate, PlateRecognitionResponse


class PlateOcrService:
    def __init__(self, languages: list[str] | None = None) -> None:
        # gpu=False para que funcione en cualquier PC/contenedor sin requerir GPU NVIDIA
        self.reader = easyocr.Reader(languages or ["en"], gpu=False)

    @staticmethod
    def _normalize_plate(text: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    @staticmethod
    def _resize_if_needed(image: np.ndarray, max_width: int = 1280) -> np.ndarray:
        height, width = image.shape[:2]
        if width <= max_width:
            return image
        scale = max_width / float(width)
        new_size = (max_width, int(height * scale))
        return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

    @staticmethod
    def _preprocess_image(image: np.ndarray) -> list[np.ndarray]:
        resized = PlateOcrService._resize_if_needed(image)
        variants: list[np.ndarray] = [resized]

        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        variants.append(enhanced)

        return variants

    def _crop_box_with_inset(
        self,
        image: np.ndarray,
        bbox: list,
        inset_ratio: float = 0.06,
    ) -> np.ndarray | None:
        pts = np.array(bbox, dtype=np.float32)
        x_min = int(np.min(pts[:, 0]))
        y_min = int(np.min(pts[:, 1]))
        x_max = int(np.max(pts[:, 0]))
        y_max = int(np.max(pts[:, 1]))

        width = x_max - x_min
        height = y_max - y_min
        if width <= 10 or height <= 10:
            return None

        # Recorte ligeramente hacia adentro para evitar bordes del marco
        inset_x = int(width * inset_ratio)
        inset_y = int(height * inset_ratio)

        h_img, w_img = image.shape[:2]
        x1 = max(0, x_min + inset_x)
        y1 = max(0, y_min + inset_y)
        x2 = min(w_img, x_max - inset_x)
        y2 = min(h_img, y_max - inset_y)

        if x2 <= x1 or y2 <= y1:
            return None

        return image[y1:y2, x1:x2]

    def recognize_from_bytes(self, image_bytes: bytes, source: str = "upload") -> PlateRecognitionResponse:
        start_time = time.perf_counter()

        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("No se pudo decodificar la imagen enviada.")

        return self._run_ocr(image=image, source=source, start_time=start_time)

    def capture_and_recognize_webcam(self, camera_index: int = 0) -> PlateRecognitionResponse:
        start_time = time.perf_counter()

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara en el índice {camera_index}.")

        try:
            for _ in range(4):
                cap.read()

            ret, frame = cap.read()
            if not ret or frame is None:
                raise RuntimeError("No se pudo capturar un frame desde la cámara.")
        finally:
            cap.release()

        return self._run_ocr(image=frame, source=f"webcam:{camera_index}", start_time=start_time)

    def _run_ocr(self, image: np.ndarray, source: str, start_time: float) -> PlateRecognitionResponse:
        candidates_map: dict[str, PlateCandidate] = {}
        allowlist = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

        for variant in self._preprocess_image(image):
            results = self.reader.readtext(variant, allowlist=allowlist)

            for bbox, text, conf in results:
                confidence = float(conf)
                if confidence < 0.20:
                    continue

                initial_norm = self._normalize_plate(text)
                candidate_text = text
                final_conf = confidence

                # Releer recorte con margen interno si tiene longitud candidata a placa
                if 5 <= len(initial_norm) <= 8:
                    cropped = self._crop_box_with_inset(variant, bbox, inset_ratio=0.06)
                    if cropped is not None:
                        refined = self.reader.readtext(
                            cropped,
                            allowlist=allowlist,
                        )
                        if refined:
                            best_refined = max(refined, key=lambda item: float(item[2]))
                            refined_norm = self._normalize_plate(best_refined[1])
                            if 5 <= len(refined_norm) <= 7:
                                candidate_text = best_refined[1]
                                final_conf = max(confidence, float(best_refined[2]))

                normalized = self._normalize_plate(candidate_text)
                if not (4 <= len(normalized) <= 7):
                    continue

                rounded_conf = round(final_conf, 4)
                existing = candidates_map.get(normalized)
                if existing is None or rounded_conf > existing.confidence:
                    candidates_map[normalized] = PlateCandidate(
                        raw_text=candidate_text.strip(),
                        normalized_text=normalized,
                        confidence=rounded_conf,
                    )

        candidates = sorted(
            candidates_map.values(),
            key=lambda c: c.confidence,
            reverse=True,
        )

        best_plate = candidates[0].normalized_text if candidates else ""
        best_confidence = candidates[0].confidence if candidates else 0.0
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return PlateRecognitionResponse(
            plate=best_plate,
            confidence=best_confidence,
            source=source,
            processing_time_ms=elapsed_ms,
            candidates=candidates,
        )