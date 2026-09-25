import asyncio
from pathlib import Path

from app.services.carImages import CarImagesService


async def download_model():
    service = CarImagesService()

    glb_data = await service.get_3d_model_file(
        make="Ford",
        model="C-Max",
        generation="c344-2015-2019"
    )

    file_path = Path(
        "models/vehicles/ford/c-max/c344-2015-2019.glb"
    )

    # Create the folders if they don't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Save the GLB
    with open(file_path, "wb") as file:
        file.write(glb_data)

    print("====================================")
    print("3D MODEL DOWNLOADED SUCCESSFULLY")
    print("File:", file_path)
    print("Size:", len(glb_data), "bytes")
    print("====================================")


if __name__ == "__main__":
    asyncio.run(download_model())