import argparse
import os
import numpy as np
from elf.io import open_file
from mmpb.attributes.region_attributes import region_attributes
from mmpb.default_config import write_default_global_config
from mmpb.release_helper import get_version
from mmpb.segmentation.validation import eval_cells, get_ignore_seg_ids
from pybdv.metadata import get_data_path

ROOT = '/g/arendt/EM_6dpf_segmentation/platy-browser-data/data'
ANNOTATIONS = os.path.join(ROOT, 'rawdata/evaluation/validation_annotations.h5')
BASELINE_ROOT = '../data.n5'
BASELINE_NAMES = ['lmc', 'mc', 'curated_lmc', 'curated_mc']
NAME = 'sbem-6dpf-1-whole-segmented-cells'


def get_label_ids(path, key):
    with open_file(path, 'r') as f:
        ds = f[key]
        max_id = ds.attrs['maxId']
    label_ids = np.arange(max_id + 1)
    return label_ids


def compute_baseline_tables(version, target, max_jobs):
    path = BASELINE_ROOT
    folder = os.path.join(ROOT, version, 'images', 'local')
    for name in BASELINE_NAMES:
        key = 'volumes/cells/%s/filtered_size' % name
        out_path = '%s.csv' % name

        if os.path.exists(out_path):
            continue

        tmp_folder = './tmp_regions_%s' % name
        config_folder = os.path.join(tmp_folder, 'configs')
        write_default_global_config(config_folder)
        label_ids = get_label_ids(path, key)
        region_attributes(path, out_path, folder, label_ids,
                          tmp_folder, target=target, max_jobs=max_jobs,
                          key_seg=key)


# TODO
def load_semantic_mapping(table_path):
    pass


def eval_seg(version, semantic_eval):
    seg_path = os.path.join(ROOT, version, 'images', 'local', NAME + '.xml')
    seg_path = get_data_path(seg_path, return_absolute_path=True)
    table_path = os.path.join(ROOT, version, 'tables', NAME, 'regions.csv')
    if seg_path.endswith('.n5'):
        key = 'setup0/timepoint0/s0'
    else:
        key = 't00000/s00/0/cells'

    if semantic_eval:
        semantic_mapping = load_semantic_mapping(table_path)
    else:
        semantic_mapping = None

    ignore_ids = get_ignore_seg_ids(table_path)
    fm, fs, tot = eval_cells(seg_path, key, ANNOTATIONS,
                             ignore_seg_ids=ignore_ids,
                             semantic_mapping=semantic_mapping)
    print("Evaluation yields:")
    print("False merges:", fm)
    print("False splits:", fs)
    print("Total number of annotations:", tot)


def eval_baselines(version, semantic_eval, target, max_jobs):
    print("Computing region tables ...")
    compute_baseline_tables(version, target, max_jobs)

    path = BASELINE_ROOT
    results = {}
    for name in BASELINE_NAMES:
        key = 'volumes/cells/%s/filtered_size' % name
        print("Run evaluation for %s ..." % name)
        table = '%s.csv' % name
        ignore_ids = get_ignore_seg_ids(table)

        if semantic_eval:
            semantic_mapping = load_semantic_mapping(table)
        else:
            semantic_mapping = None

        fm, fs, tot = eval_cells(path, key, ANNOTATIONS,
                                 ignore_seg_ids=ignore_ids,
                                 semantic_mapping=semantic_mapping)
        results[name] = (fm, fs, tot)

    for name in BASELINE_NAMES:
        print("Evaluation of", name, "yields:")
        print("False merges:", fm)
        print("False splits:", fs)
        print("Total number of annotations:", tot)
        print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, default='', help="Version to evaluate.")
    parser.add_argument("--baselines", type=int, default=0,
                        help="Whether to evaluate the baseline segmentations")
    parser.add_argument("--semantic_eval", type=int, default=0,
                        help="Whether to evaluate per region/tissue.")
    parser.add_argument('--target', type=str, default='local')
    parser.add_argument('--max_jobs', type=int, default=48)
    args = parser.parse_args()

    version = args.version
    if version == '':
        version = get_version(ROOT)

    baselines = bool(args.baselines)
    if baselines:
        print("Evaluatiing baselines")
        eval_baselines(version, bool(args.semantic_eval), args.target, args.max_jobs)
    else:
        print("Evaluating segmentation for version", version)
        eval_seg(version, bool(args.semantic_eval))


if __name__ == '__main__':
    main()
