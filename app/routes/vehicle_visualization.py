from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, FileResponse

from ..services.carImages import CarImagesService
from ..schemas.vehicle_visualization import VehicleVisualizationResponse

router = APIRouter(
    prefix="/api/vehicle-visualization",
    tags=["Vehicle Visualization"]
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
car_images_service = CarImagesService()


# ---------------------------------------------------------
# 1. Get the 3D model URL for a vehicle
# ---------------------------------------------------------
@router.get(
    "/{make}/{model}/{year}",
    response_model=VehicleVisualizationResponse
)
async def get_vehicle_visualization(
    make: str,
    model: str,
    year: int
):
    # Use the locally stored model for the 2016 Ford C-Max
    if (
        make.lower() == "ford"
        and model.lower() == "c-max"
        and year == 2016
    ):
        generation = "c344-2015-2019"

        file_path = (
            PROJECT_ROOT
            / "models"
            / "vehicles"
            / "ford"
            / "c-max"
            / f"{generation}.glb"
        )

        print("========== LOCAL VEHICLE ==========")
        print("Looking for:", file_path)
        print("Exists:", file_path.exists())
        print("===================================")

        if not file_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Local Ford C-Max 3D model not found"
            )

        return {
            "success": True,
            "make": "Ford",
            "model": "C-Max",
            "year": 2016,
            "generation": generation,
            "model_url": (
                f"http://127.0.0.1:8000"
                f"/api/vehicle-visualization/local/"
                f"Ford/C-max/{generation}"
            ),
            "watermarked": True,
            "fallback": False
        }

    # Use CarImages for vehicles that aren't locally stored
    try:
        result = await car_images_service.get_vehicle_model(
            make=make,
            model=model,
            year=year
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=404,
                detail=result.get(
                    "message",
                    "Vehicle model not found"
                )
            )

        return result

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
# ---------------------------------------------------------
# 2. Download/proxy the actual GLB model
# ---------------------------------------------------------
@router.get("/model/{make}/{model}/{generation}")
async def get_vehicle_3d_model(
    make: str,
    model: str,
    generation: str
):
    try:
        print("========== 3D MODEL REQUEST ==========")
        print("Make:", make)
        print("Model:", model)
        print("Generation:", generation)

        glb_data = await car_images_service.get_3d_model_file(
            make=make,
            model=model,
            generation=generation
        )

        print("GLB downloaded successfully")
        print("GLB size:", len(glb_data), "bytes")
        print("=======================================")

        return Response(
            content=glb_data,
            media_type="model/gltf-binary"
        )

    except Exception as e:
        print("========== 3D MODEL ERROR =============")
        print(type(e).__name__)
        print(str(e))
        print("=======================================")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve 3D model: {str(e)}"
        )


@router.get("/local/{make}/{model}/{generation}")
async def get_local_vehicle_3d_model(
    make: str,
    model: str,
    generation: str
):
    file_path = (
        Path("models")
        / "vehicles"
        / make.lower()
        / model.lower()
        / f"{generation}.glb"
    )

    print("========== LOCAL 3D MODEL ==========")
    print("Looking for:", file_path)
    print("Exists:", file_path.exists())
    print("=====================================")

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Local 3D model not found"
        )

    return Response(
        content=file_path.read_bytes(),
        media_type="model/gltf-binary"
    )