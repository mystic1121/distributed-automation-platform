# -*- encoding: utf-8 -*-

import numpy as np
import pandas as pd

get_aggregated_sum = lambda frame : frame.sum(numeric_only = True).to_dict()
#get_aggregated_by_param = lambda values, func = "mean" : round(values.mean(), 2) if func == "mean" else round(values.sum(), 2)
get_aggregated_by_param = lambda values, func: round(values.mean(), 2) if func == "mean"  else round(values.max(), 2) if ((func == "max") & (len(values)>0)) else round(values.sum(), 2)

def get_remarks(values : list, mapper : dict) -> list:
    # return list of remarks
    nom_, denom_, percent_ = map(str, values)
    
    if (nom_ == "nan") and (denom_ == "nan"):
        remark = "ERR: Formula is not yet Defined."
    elif denom_ == "nan":
        remark = None
    else:
        try:
            _ = mapper[nom_] / mapper.get(denom_, 0)
            remark = None
        except KeyError:
            remark = f"KPI Not Available: {nom_}"
        except ZeroDivisionError:
            remark = f"KPI Not Available: {denom_}"
            
    return remark

def aggregator(values : list, mapper : dict) -> float:
    nom_, denom_, percent_ = map(str, values)
    
    if (nom_ == "nan") and (denom_ == "nan"):
        result = np.nan # nothing to aggregate on
    elif denom_ == "nan":
        result = mapper.get(nom_, np.nan)
    else:
        try:
            result = mapper[nom_] / mapper.get(denom_, 0)
        except KeyError:
            result = 0
        except ZeroDivisionError:
            result = np.nan
            
    # Protect against NoneType math crashes
    if result is None:
        result = np.nan
        
    return 100 * result if str(percent_).strip().lower() == "true" else result

def aggregate_daily_ignore_reporting_type(frame : pd.DataFrame, dateparts : set) -> pd.DataFrame:
    result = dict()
    for datepart in dateparts:
        frame = frame.copy()[[column for column in frame.columns if datepart in column]]
        result[datepart] = frame.sum(axis = 1).values

    return pd.DataFrame(result)
