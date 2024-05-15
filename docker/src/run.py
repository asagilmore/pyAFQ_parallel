import os.path as op

import matplotlib.pyplot as plt
import nibabel as nib
import plotly
import pandas as pd

from AFQ.api.group import GroupAFQ
import AFQ.data.fetch as afd
import AFQ.viz.altair as ava


# Fetch the stanford_hardi dataset
afd.organize_stanford_data(clear_previous_afq="track")


tracking_params = dict(n_seeds=15000,
                       random_seeds=True,
                       rng_seed=2022,
                       trx=True)

# Create a GroupAFQ object
myafq = GroupAFQ(
    bids_path=op.join(afd.afq_home, 'stanford_hardi'),
    preproc_pipeline='vistasoft',
    tracking_params=tracking_params,
    viz_backend_spec='plotly_no_gif')


