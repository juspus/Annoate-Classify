from engine import AnnotationPluginCore
from model import Meta, AnnotationAct
import cv2
import numpy as np


class TestAgent(AnnotationPluginCore):

    def __init__(self) -> None:

        self.meta = Meta(
            name='color-percent-agent',
            description='Annotation agent used for evaluating color percent.',
            version='0.0.1'
        )

    @staticmethod
    def analyzePhoto(image_path: str) -> AnnotationAct:
        image = cv2.imread(image_path)

        redCount = 0
        greenCount = 0
        blueCount = 0

        for i in image:
            for j in i:
                pixel = np.array(j)
                maxCol = pixel.argmax()
                if maxCol == 0:
                    blueCount = blueCount + 1
                elif maxCol == 1:
                    greenCount = greenCount + 1
                elif maxCol == 2:
                    redCount = redCount + 1

        allCount = redCount + greenCount + blueCount
        redPerc = redCount/allCount
        greenPerc = greenCount/allCount
        bluePerc = blueCount/allCount

        #average = image.mean(axis=0).mean(axis=0)

        return [AnnotationAct(
                name='blue_perc',
                value=bluePerc,
                valType="double"
                ),
                AnnotationAct(
                name='green_perc',
                value=greenPerc,
                valType="double"
                ),
                AnnotationAct(
                name='red_perc',
                value=redPerc,
                valType="double"
                )]

    def invoke(self, image_path: str) -> AnnotationAct:
        analysis = self.analyzePhoto(image_path)
        return analysis
