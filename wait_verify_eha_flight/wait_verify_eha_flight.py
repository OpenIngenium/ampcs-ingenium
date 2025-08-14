
'''
This is an implementation of the builtin Verify/Wait EHA step using the Step Framework.

Authors:
    * Chris Swa

'''

import logging
from ing_lib.logs import init_console_logger
init_console_logger(logging.INFO)

from ing_lib.steps import *
from ing_lib_jpl.ampcs_lad import get_ehas
import time
import copy

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

    # Build the telemetry query/predict
    # make the query

    # Populate output values
    for i, entry in enumerate(entries):
        entry['verification_status'] = 'PASS'
        entry['entry_outputs']['entry_output_1'] = '' + str(i)
        entry['entry_outputs']['entry_output_2'] = '' + str(10*i)

        entry_output_array = entry['entry_output_array']
        for j in range(5):
            elem = {
                'entry_output_array_field_1': '' + str(j),
                'entry_output_array_field_2': '' + str(10*j),
            }
            entry_output_array.append(elem)
        
        write_output_file(output_dict, output_file_abs_path)
        logger.info(f'Entry was added: {i}')
            
        time.sleep(1)

    # set outputs        
    outputs['output_1'] = '101'
    outputs['output_2'] = '102'



    '''
    If your script has entries - evaluate them to determine overall status.
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

    msg = 'template.py has run to completion with overall status: %s' % custom_script_status
    logger.info(msg)
    output_dict['custom_script_status'] = custom_script_status

    # Report Final custom_script_status
    # TODO WRITE SERIES TO FILE
    write_output_file(output_dict, output_file_abs_path)

