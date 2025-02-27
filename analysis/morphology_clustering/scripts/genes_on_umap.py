import pandas as pd
import numpy as np
import logging
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
from pack.Clustering import plot_continuous_feature_on_umap, plot_categorical_feature_on_umap


def main():
    log_path = snakemake.log[0]
    logging.basicConfig(filename=log_path, level=logging.INFO,
                        format='%(asctime)s:%(filename)s:%(funcName)s:%(message)s')
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not os.path.isdir(snakemake.output.gene_dir):
        os.makedirs(snakemake.output.gene_dir)

    umap = np.loadtxt(snakemake.input.umap, delimiter='\t')
    table = pd.read_csv(snakemake.input.table, sep='\t')
    table = table.drop(columns=['label_id_cell', 'label_id_nucleus'])

    for val in list(table.columns):
        if 'binary' in snakemake.params.gene_assign:
            plot = plot_categorical_feature_on_umap(umap, table[val])
            if plot is None:
                logger.info('%s failed due to only having one category' % val)
                # can then pass to the continuous plotting, as this won't fail on only one category
                plot = plot_continuous_feature_on_umap(umap, table[val])

        else:
            plot = plot_continuous_feature_on_umap(umap, table[val])
        plot.set_title(val, fontsize=20)
        path = os.path.join(snakemake.output.gene_dir, val + '.png')
        plt.savefig(path)
        plt.close()


if __name__ == '__main__':
    main()
