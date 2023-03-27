from engine import AnnotationPluginCore
from model import Meta, AnnotationAct
import cv2


class TestAgent(AnnotationPluginCore):

    def __init__(self) -> None:

        self.meta = Meta(
            name='test-agent',
            description='Test agent used for testing.',
            version='0.0.1'
        )

    @staticmethod
    def analyzePhoto(image_path: str) -> AnnotationAct:
        image = cv2.imread(image_path)
        average = image.mean(axis=0).mean(axis=0)

        return [
            AnnotationAct(
                name='avg_blue',
                value=average[0],
                valType="double"
            ),
            AnnotationAct(
                name='avg_green',
                value=average[1],
                valType="double"
            ),
            AnnotationAct(
                name='avg_red',
                value=average[2],
                valType="double"
            )]

    def invoke(self, image_path: str) -> AnnotationAct:
        analysis = self.analyzePhoto(image_path)
        return analysis
