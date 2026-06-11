"""
Document quality assessment
"""

import io
from dataclasses import dataclass
from typing import Optional
import structlog
from PIL import Image
import numpy as np

logger = structlog.get_logger()


@dataclass
class QualityAssessment:
    """Result of document quality assessment"""
    overall_score: float  # 0-100
    resolution_score: float
    contrast_score: float
    sharpness_score: float
    noise_score: float

    # Flags
    is_acceptable: bool  # Overall score >= 50
    needs_preprocessing: bool
    is_likely_scanned: bool
    is_rotated: bool

    # Recommendations
    recommendations: list

    # Metadata
    width: int
    height: int
    dpi_estimate: int
    file_size_bytes: int


class QualityAssessor:
    """
    Assess document quality for OCR

    Evaluates resolution, contrast, sharpness, and noise
    to determine if preprocessing is needed.
    """

    def __init__(
        self,
        min_acceptable_score: float = 50.0,
        min_width: int = 800,
        min_height: int = 600,
    ):
        self.min_acceptable_score = min_acceptable_score
        self.min_width = min_width
        self.min_height = min_height

    async def assess(self, image_bytes: bytes) -> QualityAssessment:
        """
        Assess image quality for OCR

        Args:
            image_bytes: Image to assess

        Returns:
            QualityAssessment with scores and recommendations
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to numpy for analysis
            if image.mode != 'RGB':
                image = image.convert('RGB')

            img_array = np.array(image)
            gray = np.mean(img_array, axis=2).astype(np.uint8)

            # Calculate scores
            resolution_score = self._assess_resolution(image.width, image.height)
            contrast_score = self._assess_contrast(gray)
            sharpness_score = self._assess_sharpness(gray)
            noise_score = self._assess_noise(gray)

            # Calculate overall score (weighted average)
            overall_score = (
                resolution_score * 0.30 +
                contrast_score * 0.25 +
                sharpness_score * 0.30 +
                noise_score * 0.15
            )

            # Determine flags
            is_acceptable = overall_score >= self.min_acceptable_score
            needs_preprocessing = (
                contrast_score < 60 or
                sharpness_score < 60 or
                noise_score < 60
            )
            is_likely_scanned = self._is_likely_scanned(gray)
            is_rotated = self._detect_rotation(gray)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                resolution_score, contrast_score, sharpness_score, noise_score
            )

            # Estimate DPI
            dpi_estimate = self._estimate_dpi(image.width, image.height)

            return QualityAssessment(
                overall_score=round(overall_score, 2),
                resolution_score=round(resolution_score, 2),
                contrast_score=round(contrast_score, 2),
                sharpness_score=round(sharpness_score, 2),
                noise_score=round(noise_score, 2),
                is_acceptable=is_acceptable,
                needs_preprocessing=needs_preprocessing,
                is_likely_scanned=is_likely_scanned,
                is_rotated=is_rotated,
                recommendations=recommendations,
                width=image.width,
                height=image.height,
                dpi_estimate=dpi_estimate,
                file_size_bytes=len(image_bytes),
            )

        except Exception as e:
            logger.error("Quality assessment failed", error=str(e))
            # Return a default assessment
            return QualityAssessment(
                overall_score=50.0,
                resolution_score=50.0,
                contrast_score=50.0,
                sharpness_score=50.0,
                noise_score=50.0,
                is_acceptable=True,
                needs_preprocessing=True,
                is_likely_scanned=False,
                is_rotated=False,
                recommendations=["Unable to assess quality, proceeding with default settings"],
                width=0,
                height=0,
                dpi_estimate=150,
                file_size_bytes=len(image_bytes),
            )

    def _assess_resolution(self, width: int, height: int) -> float:
        """Assess image resolution quality"""
        min_dimension = min(width, height)

        if min_dimension >= 2000:
            return 100.0
        elif min_dimension >= 1500:
            return 90.0
        elif min_dimension >= 1000:
            return 80.0
        elif min_dimension >= 800:
            return 65.0
        elif min_dimension >= 600:
            return 50.0
        elif min_dimension >= 400:
            return 35.0
        else:
            return 20.0

    def _assess_contrast(self, gray: np.ndarray) -> float:
        """Assess image contrast"""
        # Calculate standard deviation of pixel values
        std = np.std(gray)

        # Higher std = better contrast
        if std >= 60:
            return 100.0
        elif std >= 50:
            return 85.0
        elif std >= 40:
            return 70.0
        elif std >= 30:
            return 55.0
        elif std >= 20:
            return 40.0
        else:
            return 25.0

    def _assess_sharpness(self, gray: np.ndarray) -> float:
        """Assess image sharpness using Laplacian variance"""
        # Calculate Laplacian
        laplacian = np.array([
            [0, 1, 0],
            [1, -4, 1],
            [0, 1, 0]
        ])

        from scipy import ndimage
        lap = ndimage.convolve(gray.astype(float), laplacian)
        variance = np.var(lap)

        # Higher variance = sharper image
        if variance >= 500:
            return 100.0
        elif variance >= 300:
            return 85.0
        elif variance >= 150:
            return 70.0
        elif variance >= 75:
            return 55.0
        elif variance >= 30:
            return 40.0
        else:
            return 25.0

    def _assess_noise(self, gray: np.ndarray) -> float:
        """Assess image noise level"""
        # Estimate noise using local standard deviation
        from scipy import ndimage

        # Calculate local std in 5x5 windows
        local_std = ndimage.generic_filter(
            gray.astype(float),
            np.std,
            size=5
        )
        median_local_std = np.median(local_std)

        # Lower local std = less noise = better
        if median_local_std <= 5:
            return 100.0
        elif median_local_std <= 10:
            return 85.0
        elif median_local_std <= 15:
            return 70.0
        elif median_local_std <= 20:
            return 55.0
        elif median_local_std <= 30:
            return 40.0
        else:
            return 25.0

    def _is_likely_scanned(self, gray: np.ndarray) -> bool:
        """Detect if image is likely a scanned document"""
        # Scanned documents often have high contrast and uniform background
        hist, _ = np.histogram(gray, bins=256, range=(0, 256))

        # Check for bimodal distribution (text vs background)
        # High peaks at both ends suggest scanned document
        low_peak = np.sum(hist[:30])
        high_peak = np.sum(hist[-30:])
        total = np.sum(hist)

        return (low_peak / total > 0.1) and (high_peak / total > 0.3)

    def _detect_rotation(self, gray: np.ndarray) -> bool:
        """Detect if image appears rotated"""
        # Simple heuristic: check aspect ratio
        # Rotated documents often have unusual aspect ratios
        height, width = gray.shape
        aspect_ratio = width / height

        # Most documents are portrait or landscape with reasonable ratios
        if aspect_ratio < 0.5 or aspect_ratio > 2.0:
            return True

        return False

    def _estimate_dpi(self, width: int, height: int) -> int:
        """Estimate document DPI based on dimensions"""
        # Assume standard A4 document (8.27 x 11.69 inches)
        # Calculate DPI from the larger dimension
        max_dim = max(width, height)

        if max_dim >= 3500:
            return 300
        elif max_dim >= 2400:
            return 200
        elif max_dim >= 1200:
            return 150
        else:
            return 100

    def _generate_recommendations(
        self,
        resolution: float,
        contrast: float,
        sharpness: float,
        noise: float
    ) -> list:
        """Generate preprocessing recommendations"""
        recommendations = []

        if resolution < 50:
            recommendations.append("Image resolution is low. Consider rescanning at higher DPI.")

        if contrast < 60:
            recommendations.append("Low contrast detected. Contrast enhancement recommended.")

        if sharpness < 60:
            recommendations.append("Image appears blurry. Sharpening may help.")

        if noise < 60:
            recommendations.append("High noise detected. Denoising recommended.")

        if not recommendations:
            recommendations.append("Image quality is acceptable for OCR.")

        return recommendations
