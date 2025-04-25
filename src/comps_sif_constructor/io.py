"""
Functions for dealing with i/o from COMPS
"""
import json
import pandas as pd

def load_data_brick(experiment_dir):
    """
    Load the data brick from the experiment directory
    """

    # if the folder does not exist, raise error
    if not experiment_dir.exists():
        # try default location
        raise FileNotFoundError(f"Directory {experiment_dir} does not exist")
    
    # load the data
    with open(experiment_dir / "download.id", "r") as fid:
        download_id = fid.readlines()[0]

    # load the data
    with open(experiment_dir / "output_download" / download_id / "data_brick.json", "r") as fid:
        data = json.load(fid)

    df = read_data_brick(data)

    return df    


def read_data_brick(data, drop_cols: list = []):
    """
    Read the data_brick.json JSON into a pandas DataFrame
    """
    df = None
    for exp_id, experiment in data.items():
        if df is None:
            df = {k: [] for k in experiment.keys() if k not in drop_cols}
            df.update({"exp_id": []})
        for k, v in experiment.items():
            if k not in drop_cols:
                df[k].append(v)
        df['exp_id'].append(exp_id)
    df = pd.DataFrame(df).drop(columns=['task_type'])
    return df