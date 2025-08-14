
'''
This is an implementation of the builtin Verify/Wait EHA step using the Step Framework.

Authors:
    * Chris Swa

'''

import logging
from ing_lib.logs import init_console_logger
init_console_logger(logging.INFO)

from ing_lib.steps import *
from ampcs_ing_lib.lad import get_ehas
import copy
import os


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

        verification_cond = entry_inputs.get('verificatin_cond').split(',')

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


if __name__ == '__main__':

    logger = logging.getLogger(__name__)

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
    series = {}

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

    # Write initial output
    write_output_file(output_dict, output_file_abs_path)
    logger.info('Output file was initialized')

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

    telemetry_query_func = partial(get_ehas, session_ids=[int(inputs['data_path'])])

    # make the query
    results = verify_wait_telemetry(query, telemetry_query_func, start_time=start_time, timeout=inputs.get('timeout'), lookback=inputs.get('lookback'))


    # Populate output values
    for i, entry in enumerate(entries):
        pass


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

    # Report Final custom_script_status
    # TODO WRITE SERIES TO FILE
    write_output_file(output_dict, output_file_abs_path)

