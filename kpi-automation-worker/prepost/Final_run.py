#!/usr/bin/env python
# coding: utf-8

import os
import sys
import time
import datetime as dt
import yaml
from copy import deepcopy
from tqdm import tqdm as TQ
from uuid import uuid4 as UUID
import numpy as np
import pandas as pd
from reports import *
from utilities import *
from aggregator import *

pd.set_option('display.max_rows', 50) # max. rows to show
pd.set_option('display.max_columns', 15) # max. cols to show
np.set_printoptions(precision = 3, threshold = 15) # set np options
pd.options.display.float_format = '{:,.3f}'.format # float precisions

try:
    __version__ = open("VERSION", "rt").read() # bump codecov
    print(f"Current Code Version: {__version__}") # TODO : author, contact
except Exception:
    pass

PROJECT_CODE = "prepost"
ROOT = os.path.join("..", "..") # consider root as `/` directory of repository
DATA = os.path.join(ROOT, "data", PROJECT_CODE) # the directory contains all data files, subdirectory (if any) can also be used/defined

def read_file(filepath : str, date_format : str = "%d/%m/%Y %H:%M", fillna : float = - np.inf, JCPFormat : bool = False) -> pd.DataFrame:
    data = pd.read_csv(filepath)

    # format date, time and `float` values
    data["datetime"] = data[["Date", "Time"]].apply(lambda x : f"{x['Date']} {x['Time']}", axis = 1)
    data["datetime"] = pd.to_datetime(data["datetime"], format = date_format)
    data = data.drop(columns = ["Date", "Time"]).set_index(["datetime"]).reset_index()

    if JCPFormat:
        data.fillna(fillna, inplace = True)
    else:
        for col in TQ(data.columns, desc = "type casting"):
            try:
                data[col] = data[col].apply(lambda x : fillna if (x == "-") or (x == "NaN") else float(x))
            except ValueError:
                # ignore string columns
                pass
            except TypeError:
                # ignore timestamp columns
                pass

    return data.copy() # enable deepcopy

def run_final_jcp(input_csv, template_id, report_type, jcp_format_option, report_date=None, output_dir=None, filter_time=False, time_slots=None, template_path=None, post_process=False):
    try:
        REPORT_DATE = report_date if report_date else dt.datetime.strftime(dt.datetime.strptime(time.ctime(), "%a %b %d %H:%M:%S %Y"), "%d-%m-%Y")
        REPORT_TYPE = report_type if report_type else "daily"

        today = dt.datetime.strftime(dt.datetime.strptime(time.ctime(), "%a %b %d %H:%M:%S %Y"), "%a, %b %d %Y")
        print(f"Code Execution Started on: {today}")

        UQ_IDENTIFIER = str(UUID()).upper()[:7]
        print(f"Unique Identifier for the Session: {UQ_IDENTIFIER}")

        if output_dir is None:
            OUTPUT_DIR = os.path.join(ROOT, "output", today, f"{PROJECT_CODE} #{UQ_IDENTIFIER} Report Type - {REPORT_TYPE}")
        else:
            OUTPUT_DIR = output_dir

        os.makedirs(OUTPUT_DIR, exist_ok = True)

        template = template_path
        if template is None:
            template = template_id

        INPUT_FILENAME = [input_csv]

        FILTER_TIME = filter_time
        if time_slots is None:
            TIME_RANGE_FILTER = (
                dt.time(hour = 21, minute = 0),
                dt.time(hour = 21, minute = 15),
                dt.time(hour = 21, minute = 30),
                dt.time(hour = 21, minute = 45),
                dt.time(hour = 22, minute = 0),  
            )
        else:
            TIME_RANGE_FILTER = time_slots

        # Cell Count - ignored while reading
        KPI_INFORMATION = pd.read_excel(template, sheet_name = "Summary Sheet", skiprows = 3, header = None, names = ["L0", "L1", "JCP KPI Name", "Agg. Function"])
        KPI_INFORMATION.ffill(inplace = True)

        # print additional information for code-run validations
        print(f"No. of `L0` Categories: {KPI_INFORMATION.L0.count() + 1}")
        print(f"No. of `L1` Categories: {KPI_INFORMATION.L1.count() + 1}")
        print("Aggregation Level:", KPI_INFORMATION["Agg. Function"].unique())

        # get vvip sites list and create aggregated data based on the same
        VVIP_SITES_LIST = pd.read_excel(template, sheet_name = "VVIP Sites List", skiprows = 1, header = None, usecols=[0,1], names = ["LOCATION", "CELL_ID"]).drop_duplicates()

        # print informations
        print(f"No. of Unique VVIP Sites: {VVIP_SITES_LIST.CELL_ID.nunique()}")
        print(f"No. of Unique Location List: {VVIP_SITES_LIST.LOCATION.nunique()} = {VVIP_SITES_LIST.LOCATION.unique()}")

        JCPFormat = jcp_format_option
        date_format = "%d-%m-%Y %H:%M"

        data = pd.concat([read_file(file, date_format = date_format, JCPFormat = JCPFormat) for file in INPUT_FILENAME], ignore_index = True)
        data_zero_filling = pd.concat([read_file(file, date_format = date_format, fillna = 0, JCPFormat = JCPFormat) for file in INPUT_FILENAME], ignore_index = True)

        # filter time range based on file requirement
        if FILTER_TIME:
            data["filter"] = data.datetime.apply(lambda x : x.time() in TIME_RANGE_FILTER)
            data = data[data["filter"]].drop(columns = ["filter"])
            
            data_zero_filling["filter"] = data_zero_filling.datetime.apply(lambda x : x.time() in TIME_RANGE_FILTER)
            data_zero_filling = data_zero_filling[data_zero_filling["filter"]].drop(columns = ["filter"])

        data_datepart = data.copy() # create an additional data, based on only date for daily aggregation
        data_datepart["datetime"] = data_datepart["datetime"].apply(lambda x : x.date())

        # get additional name columns based on report type
        dates = np.sort(data["datetime"].unique())
        date_parts = np.sort(data_datepart["datetime"].unique())
        if len(dates) == 0:
            return False, "No valid data could be found after parsing the date."

        pre_dates, post_date = dates[:-1], dates[-1]

        # datetime reference object for report building
        datetime_reference = {dt.datetime.strftime(dt.datetime.strptime(str(np.datetime64(datetime, 'm')), "%Y-%m-%dT%H:%M"), "%d-%m-%Y %H:%M") : datetime for datetime in dates}
        datepart_reference = {dt.datetime.strftime(dt.datetime.strptime(str(np.datetime64(datetime, 'm')), "%Y-%m-%dT%H:%M"), "%d-%m-%Y %H:%M") : datetime for datetime in date_parts}
        uq_dates = set([dt_string[:10] for dt_string in datetime_reference.keys()])

        print(f"Pre-Dates: {pre_dates}, while Post-Date is: {post_date}")
        print(f"UQ Dates from Date = {uq_dates}")

        AGGREGATED_KPI_INFORMATION = pd.read_excel(
            template, sheet_name = "aggregated", usecols = range(6),
            skiprows = 2, header = None, names = ["L0", "L1", "NOM", "DENOM", "formula", "isPercent"]
        )

        AGGREGATED_KPI_INFORMATION.L0.ffill(inplace = True)

        # 1. report for all sites
        errors_summary, summary = get_summary(data, datetime_reference, KPI_INFORMATION)
        errors_nodewise, nodewise = get_nodewise(data, datetime_reference, KPI_INFORMATION)
        errors = pd.concat([errors_summary, errors_nodewise], ignore_index = True).drop_duplicates()
        aggregated_remarks, aggregated_frame = get_aggregated(data_zero_filling, datetime_reference, AGGREGATED_KPI_INFORMATION[["NOM", "DENOM", "isPercent"]])
        _, aggregated_frame_daily_ignore_hour_always = get_aggregated(data_datepart, datepart_reference, AGGREGATED_KPI_INFORMATION[["NOM", "DENOM", "isPercent"]])

        write_excel(
            template, ROOT, PROJECT_CODE, datetime_reference,
            LOCATION_NAME = "PAN India", reports = [summary, nodewise, errors.drop_duplicates().set_index("category")],
            REPORT_DATE = REPORT_DATE, REPORT_TYPE = REPORT_TYPE,
            OUTPUT_DIR = OUTPUT_DIR, OUTPUT_FILE = f"Pre-Post QA {REPORT_TYPE.title()} Report for {REPORT_DATE} (PAN India).xlsx",
            # ..version added: add aggretaed results
            aggregated_sheet_remarks = aggregated_remarks,
            aggregated_sheet_frame = aggregated_frame,
            aggregated_daily_sheet_frame = aggregated_frame_daily_ignore_hour_always,
            post_process = post_process,
        )

        # 2. report for all mentioned vvip sites
        VVIP_SITES = data[data.Cell.isin(VVIP_SITES_LIST.CELL_ID.values)]
        VVIP_SITES_ZF = data_zero_filling[data_zero_filling.Cell.isin(VVIP_SITES_LIST.CELL_ID.values)]
        VVIP_SITES_DP = data_datepart[data_datepart.Cell.isin(VVIP_SITES_LIST.CELL_ID.values)]

        errors_summary, summary = get_summary(VVIP_SITES, datetime_reference, KPI_INFORMATION)
        errors_nodewise, nodewise = get_nodewise(VVIP_SITES, datetime_reference, KPI_INFORMATION)
        errors = pd.concat([errors_summary, errors_nodewise], ignore_index = True)
        aggregated_remarks, aggregated_frame = get_aggregated(VVIP_SITES_ZF, datetime_reference, AGGREGATED_KPI_INFORMATION[["NOM", "DENOM", "isPercent"]])
        _, aggregated_frame_daily_ignore_hour_always = get_aggregated(VVIP_SITES_DP, datepart_reference, AGGREGATED_KPI_INFORMATION[["NOM", "DENOM", "isPercent"]])

        write_excel(
            template, ROOT, PROJECT_CODE, datetime_reference,
            LOCATION_NAME = "VVIP Sites", reports = [summary, nodewise, errors.drop_duplicates().set_index("category")],
            REPORT_DATE = REPORT_DATE, REPORT_TYPE = REPORT_TYPE,
            OUTPUT_DIR = OUTPUT_DIR, OUTPUT_FILE = f"Pre-Post QA {REPORT_TYPE.title()} Report for {REPORT_DATE} (VVIP_SITES).xlsx",
            # ..version added: add aggretaed results
            aggregated_sheet_remarks = aggregated_remarks,
            aggregated_sheet_frame = aggregated_frame,
            
            aggregated_daily_sheet_frame = aggregated_frame_daily_ignore_hour_always,
            post_process = post_process,
        )

        # 3. report based on each filtered location
        for location in VVIP_SITES_LIST.LOCATION.unique():
            location=str(location)
            print(f"Processing for : {location.upper()}")
            sites_ = deepcopy(VVIP_SITES_LIST[VVIP_SITES_LIST.LOCATION == location])
            
            loc_sites = data[data.Cell.isin(sites_.CELL_ID.values)]
            loc_sites_zf = data_zero_filling[data_zero_filling.Cell.isin(sites_.CELL_ID.values)]
            loc_sites_dp = data_datepart[data_datepart.Cell.isin(sites_.CELL_ID.values)]
            
            errors_summary, summary = get_summary(loc_sites, datetime_reference, KPI_INFORMATION)
            errors_nodewise, nodewise = get_nodewise(loc_sites, datetime_reference, KPI_INFORMATION)
            errors = pd.concat([errors_summary, errors_nodewise], ignore_index = True)
            aggregated_remarks, aggregated_frame = get_aggregated(loc_sites_zf, datetime_reference, AGGREGATED_KPI_INFORMATION[["NOM", "DENOM", "isPercent"]])
            _, aggregated_frame_daily_ignore_hour_always = get_aggregated(loc_sites_dp, datepart_reference, AGGREGATED_KPI_INFORMATION[["NOM", "DENOM", "isPercent"]])

            write_excel(
                template, ROOT, PROJECT_CODE, datetime_reference,
                LOCATION_NAME = location.upper(), reports = [summary, nodewise, errors.drop_duplicates().set_index("category")],
                REPORT_DATE = REPORT_DATE, REPORT_TYPE = REPORT_TYPE,
                OUTPUT_DIR = OUTPUT_DIR, OUTPUT_FILE = f"Pre-Post QA {REPORT_TYPE.title()} Report for {REPORT_DATE} ({location.upper()}).xlsx",
                # ..version added: add aggretaed results
                aggregated_sheet_remarks = aggregated_remarks,
                aggregated_sheet_frame = aggregated_frame,
                aggregated_daily_sheet_frame = aggregated_frame_daily_ignore_hour_always,
                post_process = post_process,
            )

        return True, "Code Executed Successfully."
    except Exception as e:
        import traceback
        return False, traceback.format_exc()
    finally:
        pass

if __name__ == "__main__":
    import argparse
    import json
    import os

    print(f"--- [DEBUG] Child JCP Process Initialized (PID: {os.getpid()}) ---")

    parser = argparse.ArgumentParser(description="Run Final JCP script via CLI.")
    parser.add_argument("--input_csv", required=True, help="Path to the input CSV file.")
    parser.add_argument("--template_id", required=True, help="ID of the template.")
    parser.add_argument("--report_type", default="daily", help="Type of report (e.g., daily).")
    parser.add_argument("--jcp_format", type=str, default="false", help="JCP format option (true/false).")
    parser.add_argument("--report_date", help="Date of the report.")
    parser.add_argument("--output_dir", required=True, help="Directory for output files.")
    parser.add_argument("--template_path", required=True, help="Path to the Excel template.")
    parser.add_argument("--post_process", type=str, default="false", help="Apply cleanup post-processing (true/false).")
    
    args = parser.parse_args()

    # Convert jcp_format string to boolean
    jcp_format_bool = args.jcp_format.lower() == "true"

    success, message = run_final_jcp(
        input_csv=args.input_csv,
        template_id=args.template_id,
        report_type=args.report_type,
        jcp_format_option=jcp_format_bool,
        report_date=args.report_date,
        output_dir=args.output_dir,
        filter_time=False,
        time_slots=None,
        template_path=args.template_path,
        post_process=args.post_process.lower() == "true"
    )

    if success:
        print(f"SUCCESS: {message}")
        sys.exit(0)
    else:
        print(f"FAILED: {message}")
        sys.exit(1)