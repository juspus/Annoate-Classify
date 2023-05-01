from engine import AnnotationPluginCore
from model import Meta, AnnotationAct

from colorthief import ColorThief


class TestAgent(AnnotationPluginCore):

    def __init__(self) -> None:

        self.meta = Meta(
            name='dominant-color-agent',
            description='Annotation agent used for extracting exif data from an image.',
            version='0.0.1'
        )

    @staticmethod
    def analyzePhoto(image_path: str) -> AnnotationAct:

        # read the image data using PIL
        color_thief = ColorThief(image_path)

        palette = color_thief.get_palette(color_count=6)

        # find most frequent
        annotations = []
        count = 1
        for color in palette:

            annotations.append(AnnotationAct(
                name=f"dominant_color_palette_{count}_hex",
                value='#{:02x}{:02x}{:02x}'.format(*color),
                valType="string"
            ))

            count = count + 1

        annotations.append(AnnotationAct(
            name=f"dominant_color_hex",
            value='#{:02x}{:02x}{:02x}'.format(
                *color_thief.get_color(quality=1)),
            valType="string"
        ))

        return annotations

    def invoke(self, image_path: str) -> AnnotationAct:
        analysis = self.analyzePhoto(image_path)
        return analysis
