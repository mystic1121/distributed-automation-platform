# -*- encoding: utf-8 -*-

import numpy as np
import pandas as pd

from copy import deepcopy
from tqdm import tqdm as TQ
from aggregator import * # noqa: F403

def get_summary(frame : pd.DataFrame, datetime_reference : dict, KPI_INFORMATION : pd.DataFrame) -> [dict, pd.DataFrame]:
    output = {k : [] for k in ["L0", "L1", "JCP_KPI_NAME", "AGGREGATE_FN"] + list(datetime_reference.keys())}
    errors = {k : [] for k in ["category", "Error/Warning Message"]}

    # add report for cell count
    output["L0"].append("No. of Cells")
    output["L1"].append("No. of Cells")
    output["JCP_KPI_NAME"].append("-")
    output["AGGREGATE_FN"].append("-")

    for key, value in datetime_reference.items():
        output[key].append(frame[frame.datetime == value]["Cell"].nunique())

    # add all reports based on selected kpi informations
    for _, row in TQ(KPI_INFORMATION.iterrows(), total = KPI_INFORMATION.shape[0]):
        output["L0"].append(row["L0"])
        output["L1"].append(row["L1"])
        output["JCP_KPI_NAME"].append(row["JCP KPI Name"])
        output["AGGREGATE_FN"].append(row["Agg. Function"])

        for key, value in datetime_reference.items():
            subframe = deepcopy(frame[frame.datetime == value])
            try:
#                 output[key].append(get_aggregated_by_param(values = np.array([v for v in subframe[row["JCP KPI Name"]].values if v != - np.inf ]), func = row["Agg. Function"]))
                output[key].append(get_aggregated_by_param(values = np.array([v for v in subframe[row["JCP KPI Name"]].values if v != - np.inf and float(v) <=1000000 ]), func = row["Agg. Function"]))
            except KeyError as e:
                errors["category"].append("KeyError")
                errors["Error/Warning Message"].append(str(e))

                # if any missing/unrecogised key is found then keep blank
                output[key].append(np.nan)

    summary = pd.DataFrame(output).set_index(["L0", "L1", "JCP_KPI_NAME", "AGGREGATE_FN"])
    return pd.DataFrame(errors), summary


def get_nodewise(frame : pd.DataFrame, datetime_reference : dict, KPI_INFORMATION : pd.DataFrame) -> [dict, pd.DataFrame]:
    output = {k : [] for k in ["Cell ID", "KPI Name"] + list(datetime_reference.keys())}
    errors = {k : [] for k in ["category", "Error/Warning Message"]}
    
    for node in TQ(frame["Cell"].unique()):
        for _, row in KPI_INFORMATION.iterrows():
            subframe = deepcopy(frame[frame.Cell == node]) # first apply filter against node

            output["Cell ID"].append(node)
            output["KPI Name"].append(row["JCP KPI Name"])

            for key, value in datetime_reference.items():
                subsubframe = deepcopy(subframe[subframe.datetime == value])
                try:
                    output[key].append(get_aggregated_by_param(values = np.array([v for v in subsubframe[row["JCP KPI Name"]].values if v != - np.inf]), func = row["Agg. Function"]))
                except KeyError as e:
                    errors["category"].append("KeyError")
                    errors["Error/Warning Message"].append(str(e))

                    # if any missing/unrecogised key is found then keep blank
                    output[key].append(np.nan)

    nodewise = pd.DataFrame(output).set_index(["Cell ID", "KPI Name"])
    return pd.DataFrame(errors), nodewise

def get_aggregated(frame : pd.DataFrame, datetime_reference : dict, KPI_INFORMATION : pd.DataFrame) -> [list, pd.DataFrame]:
    aggregated_sheet_frame = dict()
    for date_key, date_value in datetime_reference.items():
        subframe = deepcopy(frame[frame.datetime == date_value])
        aggregated_sum_for_current_frame = get_aggregated_sum(subframe)

        # now get the aggregated values for each timestamp using the aggregated table
        remarks = KPI_INFORMATION.apply(lambda x : get_remarks(x, aggregated_sum_for_current_frame), axis = 1).values
        aggregated_sheet_frame[date_key] = KPI_INFORMATION.apply(lambda x : aggregator(x, aggregated_sum_for_current_frame), axis = 1).values
    aggregated_sheet_frame = pd.DataFrame(aggregated_sheet_frame)
    return remarks, aggregated_sheet_frame
