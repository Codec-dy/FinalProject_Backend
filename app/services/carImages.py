import os
import httpx
from dotenv import load_dotenv

load_dotenv()

    
class CarImagesService:

    BASE_URL = "https://carimagesapi.com"

    def __init__(self):
        self.api_key = os.getenv("CARIMAGES_API_KEY")
        self.api_secret = os.getenv("CARIMAGES_API_SECRET")

        if not self.api_key:
            raise ValueError("CARIMAGES_API_KEY is not configured")

        if not self.api_secret:
            raise ValueError("CARIMAGES_API_SECRET is not configured")

    async def get_3d_model_file(
        self,
        make: str,
        model: str,
        generation: str
    ):
        model_url = (
            f"{self.BASE_URL}/api/v1/vehicles/"
            f"{make.lower()}/"
            f"{model.lower()}/"
            f"{generation}/model"
        )

        headers = {
            "X-Api-Secret": self.api_secret
        }

        params = {
            "api_key": self.api_key,
            "redirect": "1"
        }

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True
        ) as client:

            response = await client.get(
                model_url,
                params=params,
                headers=headers
            )

            print("========== CARIMAGES RESPONSE ==========")
            print("Status:", response.status_code)
            print("URL:", response.url)
            print("Content-Type:", response.headers.get("content-type"))
            print("Size:", len(response.content))
            print("========================================")

            response.raise_for_status()

            return response.content



    async def get_vehicle_model(
        self,
        make: str,
        model: str,
        year: int
    ):
        """
        Find the correct vehicle generation and retrieve
        the corresponding 3D GLB model.
        """

        headers = {
            "X-Api-Secret": self.api_secret
        }

        # --------------------------------------------------
        # 1. Find the vehicle model in the CarImages catalog
        # --------------------------------------------------

        catalog_url = (
            f"{self.BASE_URL}/api/v1/makes/"
            f"{make.lower()}/models/{model.lower()}"
        )

        params = {
            "api_key": self.api_key
        }

        async with httpx.AsyncClient(timeout=20.0) as client:

            catalog_response = await client.get(
                catalog_url,
                params=params,
                headers=headers
            )

            catalog_response.raise_for_status()

            catalog_data = catalog_response.json()

            generations = catalog_data.get("generations", [])

            if not generations:
                return {
                    "success": False,
                    "message": "No vehicle generations found."
                }

            # --------------------------------------------------
            # 2. Find the generation corresponding to the year
            # --------------------------------------------------

            selected_generation = None

            for generation in generations:

                year_start = generation.get("year_start")
                year_end = generation.get("year_end")

                if year_start and year >= year_start:

                    if year_end is None or year <= year_end:
                        selected_generation = generation
                        break

            # --------------------------------------------------
            # 3. Fallback if exact generation isn't found
            # --------------------------------------------------

            if selected_generation is None:
                selected_generation = generations[0]

            generation_slug = selected_generation.get("slug")

            if not generation_slug:
                return {
                    "success": False,
                    "message": "Vehicle generation could not be identified."
                }

            # --------------------------------------------------
            # 4. Request the 3D model
            # --------------------------------------------------

            model_url = (
                f"{self.BASE_URL}/api/v1/vehicles/"
                f"{make.lower()}/"
                f"{model.lower()}/"
                f"{generation_slug}/model"
            )

            model_response = await client.get(
                model_url,
                params={
                    "api_key": self.api_key
                },
                headers=headers
            )

            model_response.raise_for_status()

            model_data = model_response.json()

            print("========== CARIMAGES 3D RESPONSE ==========")
            print(model_data)
            print("============================================")
            three_d_model = model_data["model"]
            print(three_d_model)

            data = {
                "success": True,
                "make": make,
                "model": model,
                "year": year,
                "generation": generation_slug,
                 "model_url": (
                    f"http://127.0.0.1:8000/api/vehicle-visualization/model/"
                    f"{make}/{model}/{generation_slug}"
                ),
                "watermarked": three_d_model["watermarked"],
                "fallback": three_d_model["fallback"]
            }
            print("======to return========")
            print(data)
            return data