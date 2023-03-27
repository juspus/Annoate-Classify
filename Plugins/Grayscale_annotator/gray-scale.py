from engine import AnnotationPluginCore
from model import Meta, AnnotationAct
import cv2
import numpy as np


class TestAgent(AnnotationPluginCore):

    def __init__(self) -> None:

        self.meta = Meta(
            name='grayscale-agent',
            description='Annotation agent used for evaluating color percent.',
            version='0.0.1'
        )

    def isgray(self, img):
        if len(img.shape) < 3:
            return True
        if img.shape[2] == 1:
            return True
        b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
        if (b == g).all() and (b == r).all():
            return True
        return False

    @staticmethod
    def analyzePhoto(image_path: str) -> AnnotationAct:
        img = cv2.imread(image_path)

        is_Grayscale = 0

        if len(img.shape) < 3:
            is_Grayscale = 1
        if img.shape[2] == 1:
            is_Grayscale = 1
        b, g, r = img[:, :, 0], img[:, :, 1], img[:, :, 2]
        if (b == g).all() and (b == r).all():
            is_Grayscale = 1

        #average = image.mean(axis=0).mean(axis=0)

        return [AnnotationAct(
                name='is_grayscale',
                value=is_Grayscale,
                valType="double"
                )]

    def invoke(self, image_path: str) -> AnnotationAct:
        analysis = self.analyzePhoto(image_path)
        return analysis
