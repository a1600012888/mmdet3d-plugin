from mmdet.datasets import DATASETS
from mmdet.datasets.custom_3d import Custom3DDataset

@DATASETS.register_module()
class MyDataset(Custom3DDataset):

    def __init__(self, ):
        pass
    