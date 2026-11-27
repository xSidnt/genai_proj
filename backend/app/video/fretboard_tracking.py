import cv2
import numpy as np


class FretboardTracker:
    """Track a calibrated quadrilateral between attempts to match the reference frame."""

    def __init__(self, reference: np.ndarray, points: np.ndarray) -> None:
        self.size = np.float32([reference.shape[1], reference.shape[0]])
        self.reference = points * self.size
        self.reference_area = cv2.contourArea(self.reference, oriented=True)
        self.detector = cv2.SIFT_create(nfeatures=650, contrastThreshold=0.012)
        self.matcher = cv2.BFMatcher(cv2.NORM_L2)
        self.reference_keys, self.reference_descriptors = self._describe(reference, self.reference)
        self.previous_gray = None
        self.corners = None
        self.reanchored = False

    def update(self, gray: np.ndarray, *, reference_frame: bool, reanchor: bool) -> np.ndarray | None:
        self.reanchored = reference_frame
        if reference_frame:
            corners = self.reference
        else:
            corners = self._follow(gray)
            if reanchor:
                matched = self._match_reference(gray, corners)
                if matched is not None:
                    corners = matched
                    self.reanchored = True

        self.previous_gray = gray
        self.corners = corners
        return corners / self.size if corners is not None else None

    def _describe(self, gray: np.ndarray, corners: np.ndarray | None, *, mask_board: bool = True):
        if corners is None:
            keypoints, descriptors = self.detector.detectAndCompute(gray, None)
            return np.float32([keypoint.pt for keypoint in keypoints]), descriptors

        x, y, width, height = cv2.boundingRect(corners)
        padding = 12 if mask_board else 35
        left, top = max(0, x - padding), max(0, y - padding)
        right = min(gray.shape[1], x + width + padding)
        bottom = min(gray.shape[0], y + height + padding)
        if right <= left or bottom <= top:
            return np.empty((0, 2), dtype=np.float32), None

        region = gray[top:bottom, left:right]
        mask = self._mask(region, corners - (left, top)) if mask_board else None
        keypoints, descriptors = self.detector.detectAndCompute(region, mask)
        return np.float32([(key.pt[0] + left, key.pt[1] + top) for key in keypoints]), descriptors

    def _match_reference(self, gray: np.ndarray, guess: np.ndarray | None) -> np.ndarray | None:
        if self.reference_descriptors is None or len(self.reference_descriptors) < 7:
            return None

        points, descriptors = self._describe(gray, guess, mask_board=False)
        if descriptors is None or len(descriptors) < 2:
            return None
        pairs = self.matcher.knnMatch(self.reference_descriptors, descriptors, k=2)
        matches = {}
        for pair in pairs:
            if len(pair) == 2 and pair[0].distance < 0.72 * pair[1].distance:
                match = pair[0]
                older = matches.get(match.trainIdx)
                if older is None or match.distance < older.distance:
                    matches[match.trainIdx] = match
        if len(matches) < 7:
            return None

        source = np.float32([self.reference_keys[match.queryIdx] for match in matches.values()])
        target = np.float32([points[match.trainIdx] for match in matches.values()])
        transform, inliers = cv2.findHomography(source, target, cv2.RANSAC, 3.0)
        if transform is None or not self._has_support(source, inliers, self.reference):
            return None
        return self._validated(cv2.perspectiveTransform(self.reference[None], transform)[0])

    def _follow(self, gray: np.ndarray) -> np.ndarray | None:
        if self.previous_gray is None or self.corners is None:
            return None

        mask = self._mask(self.previous_gray, self.corners)
        previous = cv2.goodFeaturesToTrack(self.previous_gray, 70, 0.012, 5, mask=mask)
        if previous is None or len(previous) < 7:
            return None
        next_points, forward, _ = cv2.calcOpticalFlowPyrLK(self.previous_gray, gray, previous, None)
        if next_points is None:
            return None
        returned, backward, _ = cv2.calcOpticalFlowPyrLK(gray, self.previous_gray, next_points, None)
        if returned is None:
            return None
        valid = forward.ravel().astype(bool) & backward.ravel().astype(bool)
        valid &= np.linalg.norm((returned - previous).reshape(-1, 2), axis=1) <= 1.5
        source, target = previous.reshape(-1, 2)[valid], next_points.reshape(-1, 2)[valid]
        if len(source) < 7:
            return None

        transform, inliers = cv2.estimateAffinePartial2D(source, target, ransacReprojThreshold=2.0)
        if transform is None or not self._has_support(source, inliers, self.corners):
            return None
        return self._validated(cv2.transform(self.corners[None], transform)[0])

    @staticmethod
    def _mask(gray: np.ndarray, corners: np.ndarray) -> np.ndarray:
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.rint(corners).astype(np.int32), 255)
        return mask

    @staticmethod
    def _has_support(points: np.ndarray, inliers: np.ndarray | None, corners: np.ndarray) -> bool:
        if inliers is None:
            return False
        supported = points[inliers.ravel().astype(bool)]
        if len(supported) < 6 or len(supported) < 0.5 * len(points):
            return False
        # Reject matches supported by a small patch, such as a finger crossing the neck.
        return cv2.contourArea(cv2.convexHull(supported)) >= 0.07 * cv2.contourArea(corners)

    def _validated(self, corners: np.ndarray) -> np.ndarray | None:
        if not np.isfinite(corners).all() or not cv2.isContourConvex(corners):
            return None
        ratio = cv2.contourArea(corners, oriented=True) / self.reference_area
        if not 0.35 <= ratio <= 2.8:
            return None
        return corners
