"""
Image preprocessing for OCR enhancement
"""

import io
from typing import Optional, Tuple
import structlog
from PIL import Image, ImageEnhance, ImageFilter

logger = structlog.get_logger()


class ImagePreprocessor:
    """
    Image preprocessing for better OCR results

    Applies various enhancements to improve text recognition.
    """

    def __init__(
        self,
        target_dpi: int = 300,
        contrast_factor: float = 1.2,
        sharpness_factor: float = 1.3,
    ):
        self.target_dpi = target_dpi
        self.contrast_factor = contrast_factor
        self.sharpness_factor = sharpness_factor

    async def preprocess(self, image_bytes: bytes) -> bytes:
        """
        Preprocess image for OCR

        Args:
            image_bytes: Raw image bytes

        Returns:
            Preprocessed image bytes
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Resize if too small (for better OCR)
            image = self._ensure_minimum_size(image)

            # Enhance contrast
            image = self._enhance_contrast(image)

            # Enhance sharpness
            image = self._enhance_sharpness(image)

            # Denoise
            image = self._denoise(image)

            # Convert back to bytes
            output = io.BytesIO()
            image.save(output, format='PNG', optimize=True)
            output.seek(0)

            logger.info(
                "Image preprocessed",
                original_size=len(image_bytes),
                processed_size=len(output.getvalue()),
                dimensions=image.size
            )

            return output.getvalue()

        except Exception as e:
            logger.warning("Image preprocessing failed, using original", error=str(e))
            return image_bytes

    def _ensure_minimum_size(self, image: Image.Image, min_width: int = 1000) -> Image.Image:
        """Ensure image meets minimum size for good OCR"""
        width, height = image.size

        if width < min_width:
            scale = min_width / width
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.debug("Image upscaled", original_width=width, new_width=new_size[0])

        return image

    def _enhance_contrast(self, image: Image.Image) -> Image.Image:
        """Enhance image contrast"""
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(self.contrast_factor)

    def _enhance_sharpness(self, image: Image.Image) -> Image.Image:
        """Enhance image sharpness"""
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(self.sharpness_factor)

    def _denoise(self, image: Image.Image) -> Image.Image:
        """Apply denoising filter"""
        # Use median filter for gentle denoising
        return image.filter(ImageFilter.MedianFilter(size=3))

    async def deskew(self, image_bytes: bytes) -> bytes:
        """
        Deskew a tilted image

        Args:
            image_bytes: Image that may be tilted

        Returns:
            Deskewed image bytes
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))

            # Simple deskew detection using edge detection
            # For production, consider using OpenCV with Hough transform

            # For now, just return the original
            # TODO: Implement proper deskewing

            output = io.BytesIO()
            image.save(output, format='PNG')
            output.seek(0)

            return output.getvalue()

        except Exception as e:
            logger.warning("Deskew failed", error=str(e))
            return image_bytes

    async def binarize(self, image_bytes: bytes, threshold: int = 128) -> bytes:
        """
        Convert image to binary (black and white)

        Useful for documents with poor contrast.

        Args:
            image_bytes: Input image
            threshold: Binarization threshold (0-255)

        Returns:
            Binary image bytes
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to grayscale
            gray = image.convert('L')

            # Apply threshold
            binary = gray.point(lambda x: 255 if x > threshold else 0, '1')

            # Convert back to RGB for compatibility
            rgb = binary.convert('RGB')

            output = io.BytesIO()
            rgb.save(output, format='PNG')
            output.seek(0)

            return output.getvalue()

        except Exception as e:
            logger.warning("Binarization failed", error=str(e))
            return image_bytes

    def get_image_info(self, image_bytes: bytes) -> Optional[dict]:
        """Get basic image information"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "format": image.format,
                "size_bytes": len(image_bytes),
            }
        except Exception as e:
            logger.warning("Failed to get image info", error=str(e))
            return None
