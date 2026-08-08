"""
Storage Service - Handles file uploads to Google Cloud Storage
"""

import base64
import logging
from google.cloud import storage
from config import settings
import os

logger = logging.getLogger("uvicorn.error")

class StorageService:
    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.project_id = settings.GCS_PROJECT_ID
        self._client = None

    @property
    def client(self):
        if self._client is None:
            # If PROJECT_ID is provided, use it. Otherwise, rely on default credentials.
            if self.project_id:
                self._client = storage.Client(project=self.project_id)
            else:
                self._client = storage.Client()
        return self._client

    def upload_profile_picture(self, user_id: int, base64_image: str) -> str:
        """
        Uploads a base64 encoded image to GCS and returns the public URL.
        """
        try:
            if not base64_image:
                return None

            # Extract content type and data
            if "," in base64_image:
                header, base64_data = base64_image.split(",", 1)
                content_type = header.split(":")[1].split(";")[0]
            else:
                base64_data = base64_image
                content_type = "image/png"  # Default

            image_data = base64.b64decode(base64_data)
            
            # Extension from content type
            ext = content_type.split("/")[-1] if "/" in content_type else "png"
            filename = f"profile_pics/user_{user_id}.{ext}"

            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            
            blob.upload_from_string(image_data, content_type=content_type)
            
            # Make the blob public if possible, or return the authenticated URL
            # For production, you might want to use signed URLs or make the bucket public-read
            # Here we return the standard GCS public link
            return f"https://storage.googleapis.com/{self.bucket_name}/{filename}"

        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            # Fallback: return the original base64 if upload fails (or raise)
            return base64_image

    def delete_profile_picture(self, filename: str):
        """Delete a file from GCS"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(filename)
            blob.delete()
        except Exception as e:
            logger.error(f"Failed to delete from GCS: {e}")

storage_service = StorageService()
