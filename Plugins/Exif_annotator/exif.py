from engine import AnnotationPluginCore
from model import Meta, AnnotationAct

from PIL import Image
from PIL.ExifTags import TAGS


class TestAgent(AnnotationPluginCore):

    def __init__(self) -> None:

        self.meta = Meta(
            name='exif-data-agent',
            description='Annotation agent used for extracting exif data from an image.',
            version='0.0.1'
        )

    @staticmethod
    def analyzePhoto(image_path: str) -> AnnotationAct:

        # read the image data using PIL
        image = Image.open(image_path)

        info_dict = {
            "exif_Image_Size": image.size,
            "exif_Image_Height": image.height,
            "exif_Image_Width": image.width,
            "exif_Image_Format": image.format,
            "exif_Image_Mode": image.mode,
            "exif_Image_is_Animated": getattr(image, "is_animated", False),
            "exif_Frames_in_Image": getattr(image, "n_frames", 1)
        }

        exifdata = image.getexif()

        annotaionActs = []

        for tag_id in exifdata:
            # get the tag name, instead of human unreadable tag id
            tag = TAGS.get(tag_id, tag_id)
            data = exifdata.get(tag_id)
            # decode bytes
            if isinstance(data, bytes):
                data = data.decode(errors="ignore")
            info_dict["exif_"+tag] = data

        for key, value in info_dict.items():
            annotaionActs.append(AnnotationAct(
                name=key,
                value=value,
                valType="string"
            ))

        print(annotaionActs)

        return annotaionActs

    def invoke(self, image_path: str) -> AnnotationAct:
        analysis = self.analyzePhoto(image_path)
        return analysis
