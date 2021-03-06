import mmcv
import numpy as np
from concurrent import futures as futures
from os import path as osp


class ScanNetData(object):
    """ScanNet data.

    Generate scannet infos for scannet_converter.

    Args:
        root_path (str): Root path of the raw data.
        split (str): Set split type of the data. Default: 'train'.
    """

    def __init__(self, root_path, split='train'):
        self.root_dir = root_path
        self.split = split
        self.split_dir = osp.join(root_path)
        self.classes = [
            'cabinet', 'bed', 'chair', 'sofa', 'table', 'door', 'window',
            'bookshelf', 'picture', 'counter', 'desk', 'curtain',
            'refrigerator', 'showercurtrain', 'toilet', 'sink', 'bathtub',
            'garbagebin'
        ]
        self.cat2label = {cat: self.classes.index(cat) for cat in self.classes}
        self.label2cat = {self.cat2label[t]: t for t in self.cat2label}
        self.cat_ids = np.array(
            [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 24, 28, 33, 34, 36, 39])
        self.cat_ids2class = {
            nyu40id: i
            for i, nyu40id in enumerate(list(self.cat_ids))
        }
        assert split in ['train', 'val', 'test']
        split_file = osp.join(self.root_dir, 'meta_data',
                              f'scannetv2_{split}.txt')
        mmcv.check_file_exist(split_file)
        self.sample_id_list = mmcv.list_from_file(split_file)

    def __len__(self):
        return len(self.sample_id_list)

    def get_box_label(self, idx):
        box_file = osp.join(self.root_dir, 'scannet_train_instance_data',
                            f'{idx}_bbox.npy')
        mmcv.check_file_exist(box_file)
        return np.load(box_file)

    def get_infos(self, num_workers=4, has_label=True, sample_id_list=None):
        """Get data infos.

        This method gets information from the raw data.

        Args:
            num_workers (int): Number of threads to be used. Default: 4.
            has_label (bool): Whether the data has label. Default: True.
            sample_id_list (list[int]): Index list of the sample.
                Default: None.

        Returns:
            infos (list[dict]): Information of the raw data.
        """

        def process_single_scene(sample_idx):
            print(f'{self.split} sample_idx: {sample_idx}')
            info = dict()
            pc_info = {'num_features': 6, 'lidar_idx': sample_idx}
            info['point_cloud'] = pc_info
            pts_filename = osp.join(self.root_dir,
                                    'scannet_train_instance_data',
                                    f'{sample_idx}_vert.npy')
            pts_instance_mask_path = osp.join(self.root_dir,
                                              'scannet_train_instance_data',
                                              f'{sample_idx}_ins_label.npy')
            pts_semantic_mask_path = osp.join(self.root_dir,
                                              'scannet_train_instance_data',
                                              f'{sample_idx}_sem_label.npy')

            points = np.load(pts_filename)
            pts_instance_mask = np.load(pts_instance_mask_path).astype(np.long)
            pts_semantic_mask = np.load(pts_semantic_mask_path).astype(np.long)

            mmcv.mkdir_or_exist(osp.join(self.root_dir, 'points'))
            mmcv.mkdir_or_exist(osp.join(self.root_dir, 'instance_mask'))
            mmcv.mkdir_or_exist(osp.join(self.root_dir, 'semantic_mask'))

            points.tofile(
                osp.join(self.root_dir, 'points', f'{sample_idx}.bin'))
            pts_instance_mask.tofile(
                osp.join(self.root_dir, 'instance_mask', f'{sample_idx}.bin'))
            pts_semantic_mask.tofile(
                osp.join(self.root_dir, 'semantic_mask', f'{sample_idx}.bin'))

            info['pts_path'] = osp.join('points', f'{sample_idx}.bin')
            info['pts_instance_mask_path'] = osp.join('instance_mask',
                                                      f'{sample_idx}.bin')
            info['pts_semantic_mask_path'] = osp.join('semantic_mask',
                                                      f'{sample_idx}.bin')

            if has_label:
                annotations = {}
                boxes_with_classes = self.get_box_label(
                    sample_idx)  # k, 6 + class
                annotations['gt_num'] = boxes_with_classes.shape[0]
                if annotations['gt_num'] != 0:
                    minmax_boxes3d = boxes_with_classes[:, :-1]  # k, 6
                    classes = boxes_with_classes[:, -1]  # k, 1
                    annotations['name'] = np.array([
                        self.label2cat[self.cat_ids2class[classes[i]]]
                        for i in range(annotations['gt_num'])
                    ])
                    annotations['location'] = minmax_boxes3d[:, :3]
                    annotations['dimensions'] = minmax_boxes3d[:, 3:6]
                    annotations['gt_boxes_upright_depth'] = minmax_boxes3d
                    annotations['index'] = np.arange(
                        annotations['gt_num'], dtype=np.int32)
                    annotations['class'] = np.array([
                        self.cat_ids2class[classes[i]]
                        for i in range(annotations['gt_num'])
                    ])
                info['annos'] = annotations
            return info

        sample_id_list = sample_id_list if sample_id_list is not None \
            else self.sample_id_list
        with futures.ThreadPoolExecutor(num_workers) as executor:
            infos = executor.map(process_single_scene, sample_id_list)
        return list(infos)


class ScanNetSegData(object):
    """ScanNet dataset used to generate infos for semantic segmentation task.

    Args:
        data_root (str): Root path of the raw data.
        ann_file (str): The generated scannet infos.
        split (str): Set split type of the data. Default: 'train'.
        num_points (int): Number of points in each data input. Default: 8192.
        label_weight_func (function): Function to compute the label weight.
            Default: None.
    """

    def __init__(self,
                 data_root,
                 ann_file,
                 split='train',
                 num_points=8192,
                 label_weight_func=None):
        self.data_root = data_root
        self.data_infos = mmcv.load(ann_file)
        self.split = split
        self.num_points = num_points

        self.all_ids = np.arange(41)  # all possible ids
        self.cat_ids = np.array([
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 24, 28, 33, 34, 36,
            39
        ])  # used for seg task
        self.ignore_index = len(self.cat_ids)

        self.cat_id2class = np.ones((self.all_ids.shape[0],), dtype=np.int) * \
            self.ignore_index
        for i, cat_id in enumerate(self.cat_ids):
            self.cat_id2class[cat_id] = i

        # label weighting function is taken from
        # https://github.com/charlesq34/pointnet2/blob/master/scannet/scannet_dataset.py#L24
        self.label_weight_func = (lambda x: 1.0 / np.log(1.2 + x)) if \
            label_weight_func is None else label_weight_func

    def get_seg_infos(self):
        scene_idxs, label_weight = self.get_scene_idxs_and_label_weight()
        save_folder = osp.join(self.data_root, 'seg_info')
        mmcv.mkdir_or_exist(save_folder)
        np.save(
            osp.join(save_folder, f'{self.split}_resampled_scene_idxs.npy'),
            scene_idxs)
        np.save(
            osp.join(save_folder, f'{self.split}_label_weight.npy'),
            label_weight)
        print(f'{self.split} resampled scene index and label weight saved')

    def _convert_to_label(self, mask):
        """Convert class_id in loaded segmentation mask to label."""
        if isinstance(mask, str):
            if mask.endswith('npy'):
                mask = np.load(mask)
            else:
                mask = np.fromfile(mask, dtype=np.long)
        # first filter out unannotated points (labeled as 0)
        mask = mask[mask != 0]
        # then convert to [0, 20) labels
        label = self.cat_id2class[mask]
        return label

    def get_scene_idxs_and_label_weight(self):
        """Compute scene_idxs for data sampling and label weight for loss \
        calculation.

        We sample more times for scenes with more points. Label_weight is
        inversely proportional to number of class points.
        """
        num_classes = len(self.cat_ids)
        num_point_all = []
        label_weight = np.zeros((num_classes + 1, ))  # ignore_index
        for data_info in self.data_infos:
            label = self._convert_to_label(
                osp.join(self.data_root, data_info['pts_semantic_mask_path']))
            num_point_all.append(label.shape[0])
            class_count, _ = np.histogram(label, range(num_classes + 2))
            label_weight += class_count

        # repeat scene_idx for num_scene_point // num_sample_point times
        sample_prob = np.array(num_point_all) / float(np.sum(num_point_all))
        num_iter = int(np.sum(num_point_all) / float(self.num_points))
        scene_idxs = []
        for idx in range(len(self.data_infos)):
            scene_idxs.extend([idx] * round(sample_prob[idx] * num_iter))
        scene_idxs = np.array(scene_idxs).astype(np.int32)

        # calculate label weight, adopted from PointNet++
        label_weight = label_weight[:-1].astype(np.float32)
        label_weight = label_weight / label_weight.sum()
        label_weight = self.label_weight_func(label_weight).astype(np.float32)

        return scene_idxs, label_weight
