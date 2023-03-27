import os
import glob
import math
import subprocess
import sys
from PIL import Image as PILIM
from model import Image
from multiprocessing import Pool


IMG_GLOBS = ('*.jpg', '*.jpeg', '*.png')
THUMBNAIL_SIZES = {'S': 400}
THUMBNAIL_LOAD_PATHS = {'S': 'imgs/loading_thumb_400.png'}
THUMBNAIL_SIZE_ITEMS = list(THUMBNAIL_SIZES.items())


def to_grid(arr, numCols):
    """ Convert list to grid (list of lists) """

    L = len(arr)
    numRows = math.ceil(L/numCols)
    return [
        [
            arr[row*numCols + col] if row*numCols + col < L else None
            for col in range(numCols)
        ]
        for row in range(numRows)
    ]


def list_images(folder):
    """ Return list of image filenames in folder """

    return [
        os.path.basename(f)
        for g in IMG_GLOBS
        for f in glob.glob(os.path.join(folder, g))
    ]


def list_images_db():
    """ Return list of image filenames in folder """

    return [
        f.Path for f in Image.select()
    ]


def open_image(imagePath):
    """ Display image in default viewer;
        Raise KeyError if user platform unsupported
    """

    if sys.platform == 'win32':
        os.startfile(imagePath)
    else:
        viewer = {
            'darwin': 'open',
            'linux': 'xdg-open',
        }[sys.platform]
        subprocess.run([viewer, imagePath])


def thumbnails(imgDestPair):
    """ Save PNG thumbnails in decreasing sizes """

    image, dest = imgDestPair
    im = PILIM.open(image)
    name = os.path.basename(image)
    name = os.path.splitext(name)[0] + '.png'
    for prefix, size in THUMBNAIL_SIZE_ITEMS:
        im.thumbnail((size, size))
        im.copy()
        im.save(os.path.join(dest, f'{ prefix }_{ name }'))


def backup_and_resize(image, dest, backupFolder, percent):
    """ Overwrite image with copy resized by given percent out of 100
        (eg 100px, percent = 90 -> 90px)
        and save backup copy
    """

    im = PILIM.open(image)
    name = os.path.basename(image)
    im.save(os.path.join(backupFolder, name))
    k = percent/100.0
    newSize = (round(k*im.size[0]), round(k*im.size[1]))
    im.resize(newSize).save(os.path.join(dest, name))


def make_thumbnails(src, dest, makeDest=True):
    """ Make thumbnails from src images in the dest folder 
        Return number of images processed
    """

    if makeDest:
        os.makedirs(dest)
    images = [os.path.join(src, img) for img in list_images_db(src)]
    L = len(images)
    if L < 8:
        for img in images:
            thumbnails((img, dest))
    else:
        numThreads = 4 if L < 64 else 8
        pool = Pool(numThreads)
        pool.map(thumbnails, [(img, dest) for img in images])
    return L


def image_size(filepath):
    return PILIM.open(filepath).size
