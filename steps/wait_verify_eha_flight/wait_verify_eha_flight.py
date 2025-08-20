
'''
This is an implementation of the builtin Verify/Wait EHA step using the Step Framework.

Authors:
    * Chris Swan

'''
import sys
import os
from ing_lib.logs import init_console_logger, get_logger
from datetime import datetime, timedelta
import copy
import os
import matplotlib.pyplot as plt
import random
from typing import List


init_console_logger()
logger = get_logger(__name__)
from ampcs_ing_lib.lad import get_ehas, ReturnOn
from ing_lib.steps import *

# List of defined colors (currently the TABLEU20 list)
COLORS = [
    "#4E79A7", "#A0CBE8", "#F28E2B", "#FFBE7D",
    "#59A14F", "#8CD17D", "#B6992D", "#F1CE63",
    "#499894", "#86BCB6", "#9C755F", "#D7B5A6",
    "#BAB0AB", "#D4D4D4", "#79706E", "#BAB0AB",
    "#CEDB9C", "#FF9DA7", "#B6992D", "#FF9DA7"
]

GRAPH_FILE_NAME = 'wait_verify_eha_graph.png'

# Global cache for colors that are still available
_remaining_colors: List[str] = []

AMPCS_PYTHON = os.environ.get('AMPCS_PYTHON')

# Add the path to AMPCS
sys.path.append(AMPCS_PYTHON)

def build_telemetry_query(entries, telemetry: dict = None):
    """"
    This function will build a telemetry query from the entries.
    """
    query = {}
    for entry in entries:
        entry_inputs = entry['entry_inputs']
        channel_id, channel_name = entry_inputs['flight_channel'].split(',')
        query[channel_id] = {
            'channel_name': channel_name,
            'dn_eu': entry_inputs['dn_eu'],
            'verify_on': entry_inputs['verify_on'],
            'verify_wait': entry_inputs['verify_wait']
        }

        if entry_inputs.get('bit_op') and entry_inputs.get('bit_mask'):
            query[channel_id]['bit_op'] = entry_inputs['bit_op']
            query[channel_id]['bit_mask'] = entry_inputs['bit_mask']

        verification_cond = entry_inputs.get('verification_cond').split(',')

        verification_condition= verification_cond[0]
        if verification_condition in ['RECORD','NOT_PRESENT']:
            verification_values = []
        if verification_condition in ['GREATER_THAN','LESS_THAN','EQUAL','NOT_EQUAL', 'GREATER_THAN_OR_EQUAL','LESS_THAN_OR_EQUAL','CONTAINS']:
            verification_values = [verification_cond[1]]
        if verification_condition in ['INCLUSIVE_RANGE','EXCLUSIVE_RANGE']:
            verification_values = [verification_cond[2], verification_cond[3]]

        query[channel_id]['verification_condition'] = verification_condition
        query[channel_id]['verification_values'] = verification_values

        if entry.get('verify_on')  == 'CHANGE':
            if telemetry.get(channel_id):
                query[channel_id]['prior_value'] = telemetry[channel_id]
            else:
                msg = f'Prior value for {channel_id} not located in telemetry history. Unable to verify on change.'
                logger.error(msg)
                raise InputError(msg)
        else:
            query[channel_id]['prior_value'] = None
       
    return query

# Wrapper to call get_ehas with session_ids as a keyword argument
def telemetry_query_func(query, timeout, lookback, start_time, return_on):
    """
    Calls `get_ehas` injecting the required `session_ids` keyword.
    This signature matches what `verify_wait_telemetry` expects.
    """
    return get_ehas(
        [int(inputs['data_path'])],
        query,
        timeout,
        lookback,
        start_time,
        ReturnOn.ALL
    )

def _available_colors() -> None:
    """Keeps the list of available coolors for series generation"""
    global _remaining_colors
    if not _remaining_colors:
        _remaining_colors = list(COLORS)

def pick_color():
    """
    Returns a color from the defined color palette

    Returns
    -------
    hex_color: str
        The selected color hex string

    """

    # Check that color list is initialized
    _available_colors()

    # Pick an unused color
    if _remaining_colors:
        color = random.choice(_remaining_colors)
        _remaining_colors.remove(color)
        return color

    # If all colors are used - just pick a random color from the palette
    return random.choice(COLORS)

# Helper to parse ERT strings (unchanged)
def _parse_ert(ert_str: str) -> datetime:
    ert_str = ert_str.strip().rstrip('Z')
    return datetime.strptime(ert_str, "%Y-%jT%H:%M:%S.%f")

def plot_all_channels(series: list, output_dir: str,
                     png_name: str = GRAPH_FILE_NAME):
    """
    Plot **all** channel time‑series on a single figure and save as PNG.

    Parameters
    ----------
    series : list[dict]
        List of channel dictionaries built earlier (each contains
        ``name``, ``color`` and ``data`` = [(dn, ert), …]).
    output_dir : str
        Directory where the PNG will be written.
    png_name : str, optional
        Filename (without path) for the combined plot.
    """
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    plt.figure(figsize=(12, 6))

    plotted_any = False   # <-- will stay False if no channel has valid points

    # Iterate over every channel, plotting its points
    for ch in series:
        chan_id = ch.get("name", "unknown")
        colour  = ch.get("color", "#000000")
        raw_data = ch.get("data", [])

        dn_vals = []
        ert_vals = []

        for point in raw_data:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            dn, ert = point
            try:
                ert_dt = _parse_ert(str(ert))
            except Exception as exc:
                logger.debug(f"Could not parse ERT '{ert}' for channel {chan_id}: {exc}")
                continue

            dn_vals.append(float(dn))
            ert_vals.append(ert_dt)

        if not dn_vals:
            logger.warning(f"No valid telemetry points for channel {chan_id}; skipping plot.")
            continue

        # Plot this channel’s line (with markers for visibility)
        plt.plot(ert_vals, dn_vals,
                 color=colour,
                 linewidth=2,
                 marker='o',
                 markersize=4,
                 label=f"Channel {chan_id}")
        plotted_any = True  # at least one line was drawn

    # ------------------------------------------------------------------
    # Only add a legend if something was actually plotted.
    # ------------------------------------------------------------------
    if plotted_any:
        plt.title("Telemetry – DN vs. Earth Return Time (All Channels)")
        plt.xlabel("Earth Return Time (ERT)")
        plt.ylabel("DN Value")
        plt.grid(True, which="both", ls="--", lw=0.5, alpha=0.7)
        plt.legend(title="Channels", loc="best", fontsize="small")
        plt.gcf().autofmt_xdate()
        plt.tight_layout()
    else:
        # Still produce a minimal figure so the PNG exists, but warn the user.
        plt.title("No valid telemetry data to display")
        plt.axis('off')  # hide axes

    # Save the combined image
    png_path = os.path.join(output_dir, png_name)
    plt.savefig(png_path, dpi=300)
    plt.close()

    logger.info(f"Saved combined telemetry plot → {png_path}")

if __name__ == '__main__':

    # Locate the custom script input file
    error_msg = 'USAGE: python wait_verify_eha_flight.py input_file_path output_file_path'
    input_file_abs_path, output_file_abs_path = get_input_output_paths(error_msg)
    logger.info(f'input_file_abs_path: {input_file_abs_path}')
    logger.info(f'output_file_abs_path: {output_file_abs_path}')

    # Read the input file
    logger.info('Reading custom script inputs')
    input_dict = read_input_file(input_file_abs_path)

    # Initialize output data
    inputs = copy.deepcopy(input_dict.get('inputs', []))
    variables = input_dict.get('variables', {})
    telemetry= copy.deepcopy(variables.get('telemetry', {}))
    parameters=copy.deepcopy(variables.get('parameters', {}))
    entries = copy.deepcopy(input_dict.get('entries', {}))

    # Initialize Series Data
    series = []

    outputs = {
        'start_time_date_time': '',
        'query_start': '',
        'query_end': ''
    }

    output_dict = {
        'custom_script_status': 'PENDING',
        'inputs': inputs,
        'entries': entries,
        'outputs': outputs
    }

    channels_to_graph=[]

    # Step through each entry and initialize the outputs
    for i, entry in enumerate(entries):
        entry['verification_status'] = 'PENDING'
        entry['entry_outputs'] = {
            'channel_type': '0',
            'dn_value': '0',
            'eu_value': '0',
            'dn_value': '0',
            'status_value': '0',
            'host': '0',
            'ert': '0',
            'scet': '0',
            'sclk': '0',
            'session_id': '0',
            'actual_value': '0',
            'prior_value': '0'
        }
        graphit = entry['entry_inputs'].get('graphable')
        if graphit == 'true':
            channels_to_graph.append(entry['entry_inputs'].get('flight_channel').split(',')[0])

    # Write initial output
    write_output_file(output_dict, output_file_abs_path)
    logger.info('Output file was initialized')
    # TODO REMOVE AFTER TESTING
    inputs['start_time'] = datetime.utcnow().strftime('%Y-%jT%H:%M:%S.%f')
    # Convert the start_time to a datetime object
    start_time = datetime.strptime(inputs['start_time'], '%Y-%jT%H:%M:%S.%f')
    
    # Compute the query range
    query_start = start_time - timedelta(seconds=inputs['lookback'])
    query_end = start_time + timedelta(seconds=inputs['timeout'])
    
    # Update the query range in the outputs
    outputs['start_time_date_time'] = start_time.strftime('%Y-%jT%H:%M:%S.%f')
    outputs['query_start'] = query_start.strftime('%Y-%jT%H:%M:%S.%f')
    outputs['query_end'] = query_end.strftime('%Y-%jT%H:%M:%S.%f')

    # Update the output
    write_output_file(output_dict, output_file_abs_path)

    # Build the telemetry query/predict
    query = build_telemetry_query(entries)

    # make the query
    results = verify_wait_telemetry(query, telemetry_query_func, start_time=start_time, timeout=inputs.get('timeout'), lookback=inputs.get('lookback'))

    # Populate output values
    for i, entry in enumerate(entries):
        entry_channel_id = entry['entry_inputs'].get('flight_channel').split(',')[0]
        entry_results = results['channels'].get(entry_channel_id)
        entry['entry_outputs']['channel_type'] = entry_results['channel_details'].get('channelType')
        entry['entry_outputs']['dn_value'] = entry_results['channel_details'].get('dn')
        entry['entry_outputs']['eu_value'] = entry_results['channel_details'].get('eu')
        entry['entry_outputs']['status_value'] = entry_results['channel_details'].get('status')
        entry['entry_outputs']['host'] = entry_results['channel_details'].get('host')
        entry['entry_outputs']['ert'] = entry_results['channel_details'].get('ert')
        entry['entry_outputs']['scet'] = entry_results['channel_details'].get('scet')
        entry['entry_outputs']['sclk'] = entry_results['channel_details'].get('sclk')
        entry['entry_outputs']['session_id'] = entry_results['channel_details'].get('sessionNumber')
        entry['entry_outputs']['actual_value'] = entry_results.get('actual_value')
        entry['entry_outputs']['prior_value'] = entry_results['predicts'].get('prior_value')

        if entry_channel_id in channels_to_graph:
            channel_series_data = []
            for chanval in entry_results['history']:
                #TODO need to incorporate "actual value" for now we can just use DN
                channel_series_data.append((chanval.get('dn'),chanval.get('ert')))

            channel_series = {'name': entry_channel_id,
                              'series_type': 'HORIZONTAL',
                              'color': pick_color(),
                              'data': channel_series_data,
                              'timetype': 'Earth Return Time'}

            series.append(channel_series)


    '''
    Evaluate the entries to determine overall status.
    '''
    # Review entries to generate overall status
    custom_script_status = 'PASS'
    for entry in entries:
        if entry['verification_status'] != 'PASS':
            custom_script_status = 'FAIL'
            break

    '''
    Log the successful completion and Push the final status (PASS/FAIL/ERROR) to the output_dict - 
    Ingenium watches for the status to be Not equal to PENDING 
    
    Note that you will likely have some logic to determine pass/fail (or will base it off entry verification_status)
    '''


    output_dict['custom_script_status'] = 'PASS'

    msg = f'wait_verify_eha_flight.py has run to completion with overall status: {custom_script_status}'
    logger.info(msg)
    output_dict['custom_script_status'] = custom_script_status

    # Write any series or image data
    output_dir = os.path.dirname(output_file_abs_path)
    write_series_file(series,output_dir)

    # Write image of channels graphed
    plot_all_channels(series, output_dir)

    # Report Final custom_script_status (will complete the script)
    write_output_file(output_dict, output_file_abs_path)

