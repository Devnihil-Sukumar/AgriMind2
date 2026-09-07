import ee
from datetime import datetime, timedelta
from app.config import ai_settings


class EarthEngineService:

    def __init__(self):

        self.project_id = ai_settings.GEE_PROJECT_ID
        self.initialized = False

        try:
            ee.Initialize(project=self.project_id)
            self.initialized = True
            print("[OK] Google Earth Engine initialized")

        except Exception as e:
            print(f"[WARNING] Google Earth Engine not available: {e}")
            print("  Satellite features will be disabled.")
            print("  Run 'earthengine authenticate' to set up credentials.")

    ####################################################################
    # Geometry
    ####################################################################

    def create_region(
        self,
        latitude,
        longitude,
        buffer_m=None
    ):

        if latitude is None or longitude is None:
            raise ValueError(
                "Latitude and Longitude cannot be None."
            )

        latitude = float(latitude)
        longitude = float(longitude)

        if buffer_m is None:
            buffer_m = ai_settings.SATELLITE_BUFFER_METERS

        point = ee.Geometry.Point(
            [longitude, latitude]
        )

        region = point.buffer(
            buffer_m
        ).bounds()

        return point, region

    ####################################################################
    # Sentinel-2 Cloud Mask
    ####################################################################

    def mask_clouds(self, image):

        qa = image.select("QA60")

        cloud = 1 << 10
        cirrus = 1 << 11

        mask = (
            qa.bitwiseAnd(cloud).eq(0)
            .And(
                qa.bitwiseAnd(cirrus).eq(0)
            )
        )

        return image.updateMask(mask)

    ####################################################################
    # Reflectance Scaling
    ####################################################################

    def scale_reflectance(self, image):

        optical = image.select(
            [
                "B2",
                "B3",
                "B4",
                "B8"
            ]
        ).multiply(0.0001)

        return image.addBands(
            optical,
            overwrite=True
        )

    ####################################################################
    # Collection
    ####################################################################

    def get_collection(
        self,
        latitude,
        longitude,
        days=None
    ):

        if days is None:
            days = ai_settings.SATELLITE_ANALYSIS_DAYS

        _, region = self.create_region(
            latitude,
            longitude
        )

        end_date = datetime.utcnow()

        start_date = end_date - timedelta(days=days)

        collection = (

            ee.ImageCollection(
                ai_settings.SATELLITE_COLLECTION
            )

            .filterBounds(region)

            .filterDate(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )

            .map(self.mask_clouds)

            .map(self.scale_reflectance)

            .sort("CLOUDY_PIXEL_PERCENTAGE")

        )

        return collection

    ####################################################################
    # Best Image Selection
    ####################################################################

    def get_best_image(
        self,
        latitude,
        longitude
    ):

        collection = self.get_collection(
            latitude,
            longitude
        )

        point, region = self.create_region(
            latitude,
            longitude
        )

        images = collection.toList(20)

        total = images.size().getInfo()

        if total == 0:
            raise RuntimeError(
                "No Sentinel-2 images found."
            )

        best_image = None
        metadata = None

        for i in range(total):

            image = ee.Image(images.get(i))

            info = image.getInfo()

            cloud = info["properties"].get(
                "CLOUDY_PIXEL_PERCENTAGE",
                100
            )

            if cloud <= ai_settings.SATELLITE_MAX_CLOUD_PERCENT:

                best_image = image
                metadata = info
                break

        if best_image is None:

            print(
                "No image below cloud threshold. "
                "Using least cloudy image."
            )

            best_image = ee.Image(
                images.get(0)
            )

            metadata = best_image.getInfo()

        return (
            best_image,
            metadata,
            point,
            region
        )

    ####################################################################
    # Metadata
    ####################################################################

    def acquisition_date(
        self,
        metadata
    ):

        props = metadata["properties"]

        if "system:time_start" in props:

            millis = props["system:time_start"]

            return datetime.utcfromtimestamp(
                millis / 1000
            ).strftime("%Y-%m-%d")

        return "Unknown"

    ####################################################################
    # Cloud Cover
    ####################################################################

    def cloud_cover(
        self,
        metadata
    ):

        return metadata["properties"].get(
            "CLOUDY_PIXEL_PERCENTAGE",
            None
        )

    ####################################################################
    # Valid Pixel Percentage
    ####################################################################

    def valid_pixels(
        self,
        image,
        region
    ):

        mask = (
            image.select("B8")
            .mask()
            .rename("mask")
        )

        stats = mask.reduceRegion(

            reducer=ee.Reducer.mean(),

            geometry=region,

            scale=10,

            maxPixels=1e9

        )

        value = stats.get("mask")

        if value is None:
            return 0

        value = value.getInfo()

        if value is None:
            return 0

        return round(value * 100, 2)

    ####################################################################
    # Image Summary
    ####################################################################

    def summary(
        self,
        metadata,
        image,
        region
    ):

        return {

            "acquisition_date":
                self.acquisition_date(metadata),

            "cloud_cover":
                self.cloud_cover(metadata),

            "valid_pixels":
                self.valid_pixels(
                    image,
                    region
                )

        }


earth_engine_service = EarthEngineService()