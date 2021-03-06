import glob
import os
import random
import string
import xml.etree.cElementTree as ET
from PIL import Image

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

from beetect.utils import Map


__all__ = ['BeeDatasetVid']


class BeeDatasetVid(Dataset):
    """Bee dataset pulled from yt videos"""

    def __init__(self, annot_dir, img_dir, transform=None, ext='jpg'):
        """
        Args:
            annot_dir (string): Root dir of annotation file
            img_dir (string): Root dir of folder of images
        """

        # skip folders/files starting with .
        folder_list = [f for f in os.listdir(img_dir) if not f.startswith('.')]

        self.annot_lists = {}
        self.img_dirs = {}
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        for folder_name in folder_list:
            # folder name is annot file name
            annot_file = os.path.join(annot_dir, folder_name + '.xml')
            annots, rand_prefix = self.read_annot_file(annot_file)
            self.annot_lists.update(annots)
            self.img_dirs[rand_prefix] = os.path.join(img_dir, folder_name)

        self.frame_lists = [f for f in self.annot_lists.keys()]

        # print(self.frame_lists)
        # print(self.img_dirs)
        # is_empty = False
        # for name in self.frame_lists:
        #     if len(self.annot_lists[name]) is False:
        #         is_empty = True
        #         print(name)
        # if is_empty is False:
        #     print('Not empty at all')

        self.transform = transform
        self.ext = '.' + ext

    def __len__(self):
        return len(self.frame_lists)

    def __getitem__(self, idx):
        """
        Format Doc: https://pytorch.org/tutorials/intermediate/torchvision_tutorial.html

        Format:
            image: PIL image of size (H, W)
            target: dict {
                boxes (list[N, 4]): [x0, y0, x1, y1] (N bounding boxes)
                labels (Int64[N])
                image_id (Int64[1]): unique for all images
            }
        """

        if torch.is_tensor(idx):
            idx = idx.tolist()

        pframe = self.frame_lists[idx]
        pre, frame = pframe.split('_')
        img_dir = self.img_dirs[pre]
        frame_path = os.path.join(img_dir, frame + self.ext)

        image = Image.open(frame_path).convert('RGB')
        boxes = self.annot_lists[pframe]
        num_boxes = len(boxes)

        # there is only one label for all frames (bee body)
        labels = torch.ones((num_boxes,), dtype=torch.int64)
        image_id = torch.tensor([idx], dtype=torch.int64)

        target = Map({})
        target.boxes = boxes # later changed to tensor
        target.labels = labels
        target.image_id = image_id

        if self.transform:
            image, target = self.transform(image, target)

        return image, target

    def read_annot_file(self, annot_file):
        """
        Read annotation file .xml exported from cvat (PASCAL VOC format)
        and return annotations by frames. Currently doesn't support
        tracking each object by id.

        Args:
            annot_file (string): Path to the annotation file
        """
        tree = ET.parse(annot_file)
        root = tree.getroot()
        annot_frames = {} # annotated frames

        # generate unique prefix for identification
        prefix_len = 4
        rand_prefix = ''.join(random.choices(string.ascii_letters + string.digits, k=prefix_len))

        # a track contains all annotated frames for an object
        tracks = [c for c in root if c.tag == 'track']

        for track in tracks:
            obj_id = track.attrib['id'] # assigned object id across all frames

            # box is essentially an annotated frame (of an object)
            for box in track:
                attr = box.attrib

                # skip object outside the frame (include occluded)
                if attr['outside'] != '0': continue

                frame = attr['frame'] # annotated frame id
                pframe = '{}_{}'.format(rand_prefix, frame) # _ separater
                # bbox position top left, bottom right
                bbox = [attr['xtl'], attr['ytl'], attr['xbr'], attr['ybr']]
                bbox = [float(n) for n in bbox] # string to float
                if len(bbox) is False:
                    print(pframe, bbox)

                # set up frame obj in frames
                if pframe not in annot_frames:
                    annot_frames[pframe] = []

                annot_frames[pframe].append(bbox)

        # print('=' * 20)
        # print(rand_prefix)
        # print(annot_frames)
        # print('=' * 20)

        return annot_frames, rand_prefix
