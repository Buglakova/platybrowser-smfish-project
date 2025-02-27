import argparse
import json
import multiprocessing
import os
from glob import glob
from common import RAW_PATH, RAW_KEY, BOUNDARY_PATH, BOUNDARY_KEY


def preprocess_for_project(project_folder, tool_project_folder):
    from mmpb.segmentation.correction.preprocess import preprocess_from_paintera_project
    raw_path = RAW_PATH
    raw_root_key = RAW_KEY

    work_scale = 2
    # FIXME fails for scale > 0
    preprocess_scale = 0

    boundary_path = BOUNDARY_PATH
    boundary_key = BOUNDARY_KEY + '/s%i' % preprocess_scale

    out_key = 'volumes/segmentation_before_splitting'

    target = 'local'
    n_cores = multiprocessing.cpu_count()
    max_jobs = min(48, n_cores)

    project_id = project_folder.rstrip('/')[-2:]
    project_id = int(project_id)

    this_path = os.path.abspath(__file__)
    this_path = os.path.split(__file__)[0]
    tmp_folder = os.path.join(this_path, 'tmps/tmp_project%i_splitting' % project_id)
    roi_file = os.path.join(this_path, 'configs/rois.json')

    # load this roi
    with open(roi_file) as f:
        rois = json.load(f)
    roi_begin, roi_end = rois[str(project_id)]

    if preprocess_scale > 0:
        scale_factor = 2 ** preprocess_scale
        roi_begin = [rb // scale_factor for rb in roi_begin]
        roi_end = [re // scale_factor for re in roi_end]

    preprocess_from_paintera_project(project_folder, tool_project_folder,
                                     raw_path, raw_root_key,
                                     boundary_path, boundary_key,
                                     out_key, preprocess_scale, work_scale,
                                     tmp_folder, target, max_jobs,
                                     roi_begin=roi_begin, roi_end=roi_end)


# TODO add support for projecting labels to background
def export_to_paintera(tool_project_folder):
    from mmpb.segmentation.correction import (export_node_labels, remove_flagged_ids,
                                              read_paintera_max_id, write_paintera_max_id)

    print("Exporting results from splitting workflow to paintera")
    project_folder = os.path.split(tool_project_folder)[0]
    paintera_attrs = os.path.join(project_folder, 'attributes.json')
    assert os.path.exists(paintera_attrs), paintera_attrs

    path = os.path.join(project_folder, 'data.n5')
    pt_assignment_key = 'volumes/paintera/fragment-segment-assignment'

    max_id = read_paintera_max_id(project_folder)
    max_id, resolved_ids = export_node_labels(path, pt_assignment_key, project_folder, max_id)
    remove_flagged_ids(paintera_attrs, resolved_ids)
    write_paintera_max_id(project_folder, max_id)


def run_splitting_tool(tool_project_folder):
    from mmpb.segmentation.correction import CorrectionTool
    config_file = os.path.join(tool_project_folder, 'correct_false_merges_config.json')
    assert os.path.exists(config_file), "Could not find %s, something in pre-processing went wrong!" % config_file
    print("Start splitting tool")
    splitter = CorrectionTool(tool_project_folder)
    done = splitter()
    if done:
        export_to_paintera(tool_project_folder)


def main(path):
    tool_project_folder = os.path.join(path, 'splitting_tool')
    if os.path.exists(tool_project_folder):
        run_splitting_tool(tool_project_folder)
    else:
        # try catch around this and clean up if something goes wrong ?
        preprocess_for_project(path, tool_project_folder)


def debug(path):
    import numpy as np
    import z5py
    from heimdall import view

    p = os.path.join(path, 'data.n5')

    p_raw = '/g/arendt/EM_6dpf_segmentation/platy-browser-data/data/rawdata/sbem-6dpf-1-whole-raw.n5'
    k_raw = 'setup0/timepoint0/s1'
    f_raw = z5py.File(p_raw, 'r')
    ds_raw = f_raw[k_raw]
    ds_raw.n_threads = 8

    f_seg = z5py.File(p)
    k_seg = 'volumes/segmentation_before_splitting'
    ds_seg = f_seg[k_seg]
    ds_seg.n_threads = 8
    assert ds_raw.shape == ds_seg.shape, "%s, %s" % (ds_raw.shape, ds_seg.shape)

    proj_id = int(path[-2:])
    this_path = os.path.abspath(__file__)
    this_path = os.path.split(__file__)[0]
    roi_file = os.path.join(this_path, 'configs/rois.json')
    with open(roi_file) as f:
        rois = json.load(f)
    roi_begin, roi_end = rois[str(proj_id)]

    halo = [50, 512, 512]
    center = [rb + (re - rb) // 2 for re, rb in zip(roi_begin, roi_end)]
    print(roi_begin, roi_end)
    print(center)
    bb = tuple(slice(ce - ha, ce + ha) for ce, ha in zip(center, halo))
    print(bb)

    raw = ds_raw[bb]
    seg = ds_seg[bb]
    view(raw, seg)
    return

    k = 'morphology'
    with z5py.File(p, 'r') as f:
        ds = f[k]
        m = ds[:]
    starts = m[:, 5:8]
    stops = m[:, 8:11]

    print(starts.min(axis=0))
    print(starts.max(axis=0))
    print()
    print(stops.min(axis=0))
    print(stops.max(axis=0))
    return

    seg_root_key = 'volumes/paintera'
    ass_key = os.path.join(seg_root_key, 'fragment-segment-assignment')
    with z5py.File(p, 'r') as f:
        assignments = f[ass_key][:].T
        seg_ids = assignments[:, 1]
    unique_ids = np.unique(seg_ids)
    if unique_ids[0] == 0:
        unique_ids = unique_ids[1:]
    unique_ids = unique_ids

    # print(len(starts))
    # print(unique_ids.max())
    # return

    attrs_p = os.path.join(path, 'attributes.json')
    with open(attrs_p) as f:
        attrs = json.load(f)

    seg_state = attrs['paintera']['sourceInfo']['sources'][1]['state']
    locked_ids = seg_state['lockedSegments']

    flagged_ids = np.array(list(set(unique_ids.tolist()) - set(locked_ids)))
    flagged_ids = flagged_ids[np.isin(flagged_ids, unique_ids)].tolist()

    for flag_id in flagged_ids:
        print(flag_id)
        if flag_id >= len(starts):
            print("%i is out of bounds %i" % (flag_id, len(starts)))
            continue
        print(starts[flag_id])
        print(stops[flag_id])
        print()


def debug_extraction(path):
    from mmpb.segmentation.correction.export_node_labels import check_exported

    scale = 2

    data_path = os.path.join(path, 'data.n5')
    assignment_key = 'volumes/paintera/fragment-segment-assignment'
    old_assignment_key = 'volumes/paintera/fragment-segment-assignment.1585686151-419452'

    table_key = 'morphology'
    scale_factor = 2 ** scale

    raw_path = RAW_PATH
    raw_key = RAW_KEY + '/s%i' % (scale + 1,)

    ws_path = data_path
    ws_key = 'volumes/paintera/data/s%i' % scale

    pattern = os.path.join(path, 'splitting_tool', 'results', '*.npz')
    seg_ids = glob(pattern)
    seg_ids = [os.path.splitext(os.path.split(seg_id)[1])[0]
               for seg_id in seg_ids]
    seg_ids = [int(seg_id) for seg_id in seg_ids]

    print("Start checks for %i objects" % len(seg_ids))
    check_exported(data_path, old_assignment_key, assignment_key,
                   data_path, table_key, scale_factor,
                   raw_path, raw_key, ws_path, ws_key, seg_ids)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str)
    parser.add_argument('--debug_mode', default=0, type=int)
    args = parser.parse_args()

    path = args.path
    assert os.path.exists(path), "Cannot find valid project @ %s" % path
    debug_mode = int(args.debug_mode)

    if debug_mode:
        # debug(path)
        debug_extraction(path)
    else:
        main(path)
