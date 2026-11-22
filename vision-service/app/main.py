from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from app.ocr_service import PlateOcrService
from app.schemas import PlateRecognitionResponse

app = FastAPI(
    title="Parking System",
    version="0.1.0",
    description="Servicio de captura y reconocimiento óptico de placas para parqueadero",
)

ocr_service = PlateOcrService(languages=["en"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/plate/recognize", response_model=PlateRecognitionResponse)
async def recognize_plate(file: UploadFile = File(...)) -> PlateRecognitionResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen válida.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="La imagen está vacía.")

    try:
        return ocr_service.recognize_from_bytes(image_bytes=image_bytes, source=f"upload:{file.filename}")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Error procesando la imagen: {ex}") from ex


@app.post("/api/plate/capture-webcam", response_model=PlateRecognitionResponse)
def capture_webcam(camera_index: int = Query(default=0, ge=0)) -> PlateRecognitionResponse:
    try:
        return ocr_service.capture_and_recognize_webcam(camera_index=camera_index)
    except RuntimeError as ex:
        raise HTTPException(status_code=422, detail=str(ex)) from ex
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Error en cámara: {ex}") from ex