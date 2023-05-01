import os.path

from engine import AnnotationPluginCore
from model import Meta, AnnotationAct
import cv2
import numpy as np
import torch
from torch import nn
import torchvision.models as models
import albumentations as A
from albumentations.pytorch import ToTensorV2
import torchvision.transforms as transforms
import onnxruntime
from PIL import Image


class TestAgent(AnnotationPluginCore):

    def __init__(self) -> None:
        self.meta = Meta(
            name='sku-agent',
            description='Annotation agent used for classifying sku.',
            version='0.0.1'
        )

    @staticmethod
    def analyzePhoto(image_path: str) -> AnnotationAct:

        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

        image = Image.open(image_path)

        if image.mode != 'RGB':
            return None

        image_tensor = transform(image)
        image_tensor = image_tensor.unsqueeze(0)
        # Load the ONNX model
        model_path = "Plugins\Sku_annotator\model.onnx"
        session = onnxruntime.InferenceSession(model_path)

        # Run the model with the image tensor as input
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        output = session.run([output_name], {input_name: image_tensor.numpy()})

        # Get the confidence scores for each class
        scores = np.exp(output[0]) / np.sum(np.exp(output[0]))

        sku_name_dict = {'Sku_0': 'Banana',
                         'Sku_1': 'Lemons',
                         'Sku_2': 'Apples',
                         'Sku_3': 'BIO bananas',
                         'Sku_4': 'Carrots',
                         'Sku_5': 'Tomatoes',
                         'Sku_6': 'Red onions',
                         'Sku_7': 'Potatoes',
                         'Sku_8': 'Onions',
                         'Sku_9': 'Zucchini',
                         'Sku_10': 'Long-fruited cucumbers',
                         'Sku_11': 'Limes',
                         'Sku_12': 'Oranges', }

        annotations = []

        skuNames = list(sku_name_dict.values())
        for i, score in enumerate(scores[0]):

            annotations.append(AnnotationAct(
                name=f'Sku_{skuNames[i]}_confidence_score',
                value=score,
                valType="double"
            ))

        return annotations

    def invoke(self, image_path: str) -> AnnotationAct:
        analysis = self.analyzePhoto(image_path)
        return analysis
