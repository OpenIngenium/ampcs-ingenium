"""
This library contains functions and classes to interface with AMPCS via the lad.

Authors:
    * Chris Swan
    * Hongman Kim
"""

#################################################### Imports ####################################################

import os
import sys
# AMPCS lad library
AMPCS_PYTHON = os.environ.get('AMPCS_PYTHON')
# Add the path to AMPCS
sys.path.append(AMPCS_PYTHON)
from lad import client, gdsclient
from enum import Enum
from datetime import datetime, timedelta
from operator import itemgetter
import traceback
import time
import logging


logger = logging.getLogger(__name__)

#################################################### Constants ####################################################

# environment variable: _LAD_HTTPS can either be True or False and will be used as an argument value in the LadClient function

# environment variable: LAD_HOST should be in the format "<hostname>.jpl.nasa.gov"
_LAD_HOST = os.environ.get("LAD_HOST", os.environ.get("HOSTNAME"))
_LAD_PORT = int(os.environ.get("LAD_PORT", 8887))
_LAD_TIMEOUT_SEC = 60

# These are set to the defaults of the AMPCS lad client. They can be increased to capture more information but that
# can impact performance (especially when doing large/wildcard queries)
_LAD_EHA_MAX_RESULTS = int(os.environ.get("LAD_EHA_MAX_RESULTS", 10))
_LAD_EVR_MAX_RESULTS = int(os.environ.get("LAD_EVR_MAX_RESULTS", 100))
DOY_TIME_FORMAT = "%Y-%jT%H:%M:%S.%f"

# The amount of time in seconds the library will query after the query window
_AMPCS_QUERY_MARGIN = 5

#################################################### Classes ####################################################

class QueryError(Exception):
    """
    Error in querying the GLAD
    """
    pass

class TimeType(str, Enum):
    ERT = 'ERT'
    SCET = 'SCET'
    SCLK = 'SCLK'


class FSWvsSSE(str, Enum):
    FSW = 'FSW'
    SSE = 'SSE'


class RealTimeRecorded(str, Enum):
    REALTIME = 'REALTIME'
    RECORDED = 'RECORDED'


class ReturnOn(str, Enum):
    ANY = 'ANY'
    ALL = 'ALL'

#################################################### Functions ####################################################

def get_lad_https_protocol():
    """
    This function will query an env variable (LAD_HTTPS) and determine if LAD should use https

    Returns
    -------
    True/False
    """

    lad_protocol = os.environ.get("LAD_HTTPS", "")

    # in order to properly set this argument variable in the LadClient() function.
    # The environment variable needs to be cast into the boolean type.
    if lad_protocol.lower() == "true":
        return True
    else:
        return False


_LAD_HTTPS = get_lad_https_protocol()

def query_evrs(session_ids, timeout=None, evr_names=[], evr_ids=[],
               evr_levels=[], evr_messages=[], time_type=TimeType.ERT,
               start_time=None, end_time=None, fsw_sse=None, rt_rec=None,
               max_results=_LAD_EVR_MAX_RESULTS):
    """
      Queries for EVR using GLAD. More than one EVR name can be queried.

      Parameters
      ------------------
      session_ids: list of int
        AMPCS session ids Note that multi-session queries, while possible, have max_result implications and are not
        handled by the functions that evaluate the results.
      timeout: int
        Time to wait in seconds before timeout
      evr_names: list of str
        Names of evrs to match. Accepts the '*' wildcard.
      evr_ids: list of str
        EVR event ids
      evr_levels: list of str
        EVR levels
      evr_messages: list of str
        List of EVR message regular expressions
      time_type: TimeType
        Should be one of TimeType
      start_time: str
        Begin time of query range (Time format for all time types except SCLK is YYYY-DOYThh:mm:ss.ttt)
      end_time: str
        End time of query range (Time format for all time types except SCLK is YYYY-DOYThh:mm:ss.ttt)
      fsw_sse: FSWvsSSE
        Restrict query to fsw or sse channels
      rt_rec: RealTimeRecorded
        Restrict query to either real time or recorded telemetry
      max_results: int
        The max number of results to return (per EVR Level). Note that for large queries this can impact performance.

      Returns
      ------------------
      lad_results: list of dict
        list of evrs in dict (most recent first)
      """

    evrq = client.EvrQuery()

    # General LAD query parameters

    evrq.setMaxResults(max_results)

    for session_id in session_ids:
        evrq.addSessionNumber(session_id)

    if time_type == TimeType.ERT:
        evrq.useErt()
    elif time_type == TimeType.SCET:
        evrq.useScet()
    elif time_type == TimeType.SCLK:
        evrq.useSclk()

    if fsw_sse == FSWvsSSE.FSW:
        evrq.fswOnly()
    elif fsw_sse == FSWvsSSE.SSE:
        evrq.sseOnly()

    if rt_rec == RealTimeRecorded.REALTIME:
        evrq.realtimeOnly()
    elif rt_rec == RealTimeRecorded.RECORDED:
        evrq.recordedOnly()

    if end_time is not None:
        evrq.before(end_time)

    if start_time is not None:
        evrq.after(start_time)

    if timeout is not None:
        lad_timeout = timeout
    else:
        lad_timeout = _LAD_TIMEOUT_SEC

    ##### EVR query parameters #####

    for evr_name in evr_names:
        evrq.addEvrName(evr_name)

    for evr_id in evr_ids:
        evrq.addEventId(evr_id)

    for evr_level in evr_levels:
        evrq.addEvrLevel(evr_level)

    # Note that Ingenium found an issue with EVR message filtered via LAD query if EVR messages had carriage returns.
    # Ingenium worked around it (by adding their own filter post query) but this was some time ago (2019)
    # For now we will assume it is fixed
    for evr_message in evr_messages:
        evrq.addMessagePattern(evr_message)

    logger.debug(f'Set realtime EVR query internal timeout alarm to {lad_timeout} seconds')

    logger.debug(f'Querying realtime evr at time: {datetime.utcnow().isoformat()}')
    logger.debug(f'Opening connection to GlobalLad. https={_LAD_HTTPS} Host={_LAD_HOST} Port={_LAD_PORT}')
    c = client.LadClient(host=_LAD_HOST, port=_LAD_PORT, https=_LAD_HTTPS)
    logger.debug(f'URI:{str(evrq.getUri())}')
    logger.debug(f'Parameters:{str(evrq.getParams())}')
    lad_results = gdsclient.flattenDict(c.fetchEvrs(evrq))
    logger.debug(f'Got response at time: {datetime.utcnow().isoformat()}')

    return lad_results


def query_ehas(session_ids, channel_ids, timeout=None,
               time_type=TimeType.ERT, start_time=None, end_time=None, fsw_sse=None,
               rt_rec=None, max_results=_LAD_EHA_MAX_RESULTS):
    """
    Queries for EHA using GLAD. More than one EHA ids can be queried.


    Parameters
    ------------------
    session_ids: list of int
        AMPCS session ids Note that multi-session queries, while possible, have max_result implications and are not
        handled by the functions that evaluate the results.
    channel_ids: list of str
      EHA channel ids
    timeout: int
      Time to wait in seconds before timeout
    time_type: TimeType
      Should be one of the TimeTypes (ERT Default)
    start_time: str
      Begin time of query range (Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt)
    end_time: str
      End time of query range (Time format for all time types except SCLK (in GMT) is YYYY-DOYThh:mm:ss.ttt)
    fsw_sse: FSWvsSSE
      Restrict query to fsw or sse channels
    rt_rec: RealTimeRecorded
        Restrict query to either real time or recorded telemetry
    max_results: int
        The max number of results to return (per channel). Note that for large queries this can impact performance.

    Returns
    ------------------
    lad_results: list of dict
        List of channels in dict format (most recent first)
    """

    ehaq = client.ChanValQuery()

    ##### General LAD query parameters #####

    ehaq.setMaxResults(max_results)

    for session_id in session_ids:
        ehaq.addSessionNumber(session_id)

    if time_type == TimeType.ERT:
        ehaq.useErt()
    elif time_type == TimeType.SCET:
        ehaq.useScet()
    elif time_type == TimeType.SCLK:
        ehaq.useSclk()

    if fsw_sse == FSWvsSSE.FSW:
        ehaq.fswOnly()
    elif fsw_sse == FSWvsSSE.SSE:
        ehaq.sseOnly()

    if rt_rec == RealTimeRecorded.REALTIME:
        ehaq.realtimeOnly()
    elif rt_rec == RealTimeRecorded.RECORDED:
        ehaq.recordedOnly()

    if end_time is not None:
        ehaq.before(end_time)

    if start_time is not None:
        ehaq.after(start_time)

    if timeout is not None:
        lad_timeout = timeout
    else:
        lad_timeout = _LAD_TIMEOUT_SEC

    ##### EHA query parameters #####

    for channel_id in channel_ids:
        ehaq.addChannelId(channel_id)

    logger.debug(f'Set realtime EHA query internal timeout to {lad_timeout} seconds')

    # Query the LAD

    logger.debug(f'Querying {rt_rec} eha at time: {datetime.utcnow().isoformat()}')
    logger.debug(f'Opening connection to GlobalLad. https={_LAD_HTTPS} Host={_LAD_HOST} Port={_LAD_PORT}')
    c = client.LadClient(host=_LAD_HOST, port=_LAD_PORT, https=_LAD_HTTPS)
    logger.debug(f'URI: {str(ehaq.getUri())}')
    logger.debug(f'Parameters: {str(ehaq.getParams())}')
    lad_results = gdsclient.flattenDict(c.fetchChannels(ehaq))
    logger.debug(f'Got response at time: {datetime.utcnow().isoformat()}')

    return lad_results


def get_ehas(session_ids, channel_ids, timeout, lookback, start_time=None,
             fsw_sse=None, rt_rec=RealTimeRecorded.REALTIME,
             max_results=_LAD_EHA_MAX_RESULTS, return_on=ReturnOn.ALL):
    """
    This function will query the GLAD for specific channels and will continue to query until channels are found or the
    timeout is reached. It will then format the data.

    Note that this function only operates with ERT.

    Parameters
    ----------
    session_ids: list of int
        AMPCS session ids Note that multi-session queries, while possible, have max_result implications and are not
        handled by the functions that evaluate the results.
    channel_ids: list of str
        Channels to query (by channel id). Does support wild cards but some of the aggregate results (determining
        if all channels have a measurement or which channels don't) are not supported.
    timeout: int
        This is a combination of the time to attempt to query before giving up and defines the time range to query.
    lookback: int
        How much time to "look back" from now for the channel query
    start_time: datetime object
        The start time of the query (use now if not provided)
    fsw_sse: FSWvsSSE
        Whether to query FSW or SSE channels
    rt_rec: RealTimeRecorded
        Whether to query Real Time or Recorded channels
    max_results: int
        The max number of results to query (note that this will be computed if not provided)
    return_on: ReturnOn
        This controls whether the function will return when it has results for any channels or it will wait for
        all channels to have data. Note that this can impact the most recent result (e.g. one channel could change
        while waiting for all channels to be located). ANY is used if a wildcard is used for channel_ids.

    Returns
    -------
        List of EHA objects ordered by ERT in descending order. (the first is the latest)
    """

    # Compute the timeframe

    if not start_time:
        start_time = datetime.utcnow()

    query_start_time = start_time - timedelta(seconds=lookback)
    query_end_time = start_time + timedelta(seconds=timeout)

    # Check if the query includes a wild card
    for channel_id in channel_ids:
        if '*' in channel_id:
            wild_card = True
            break
        else:
            wild_card = False

    # Query and process the results

    # This loop will always query at least once and then will query until
    # The timeout is reached or sufficient results have been found (based on return_on)

    time_out_time = query_end_time + timedelta(seconds=_AMPCS_QUERY_MARGIN)

    query_once = False
    while (not query_once) or datetime.utcnow() < time_out_time:
        query_once = True
        # Queries the channel
        try:
            query_results = query_ehas(session_ids,
                                       channel_ids,
                                       start_time=query_start_time.strftime(DOY_TIME_FORMAT),
                                       end_time=query_end_time.strftime(DOY_TIME_FORMAT),
                                       fsw_sse=fsw_sse,
                                       rt_rec=rt_rec,
                                       max_results=max_results)
        except:
            msg = "Encountered and error querying GLAD for channels"
            logger.error(msg)
            logger.error(traceback.format_exc())
            raise QueryError(msg)

        # Create the return structure
        results = {'total_measurements': 0,
                   'measurements_for_all': True,
                   'channels_with_no_data': [],
                   'channels': {}}

        # Create the channel structure if not a wild card
        if not wild_card:
            for channel_id in channel_ids:
                results['channels'][channel_id] = []

        # if results are returned process them
        if query_results:

            # Process the results
            for result in query_results:
                results['total_measurements'] += 1

                # If the channel query is a wildcard - the list of channels will be determined based on the data
                if wild_card:
                    if results['channels'].get(result.get('channelId')) is None:
                        results['channels'][result.get('channelId')] = []

                results['channels'][result.get('channelId')].append(result)

            # Sort the ERT in descending order for each channel (if data is present)
            for channel in results['channels'].keys():
                sorted(results['channels'][channel], key=itemgetter('ert'), reverse=True)

                # If no data is present for a given channel set measurements_for_all to False
                if len(results['channels'][channel]) == 0:
                    results['measurements_for_all'] = False
                    results['channels_with_no_data'].append(channel)

            # If return_on is ANY and there are any results - return
            if return_on == ReturnOn.ANY and results['total_measurements'] > 0:
                msg = f"Returning {results['total_measurements']} measurements return on: {return_on}"
                logger.debug(msg)
                return results

            # If return_on is ALL and measurements_for_all is True - return
            if return_on == ReturnOn.ALL and results['measurements_for_all']:
                msg = f"Returning {results['total_measurements']} measurements return on: {return_on}"
                logger.debug(msg)
                return results

        # Wait a second to avoid hammering the GLAD
        time.sleep(1)

    if results['total_measurements'] == 0:
        msg = f"No EHA measurements were located for channels: {channel_ids} between: {query_start_time.strftime(DOY_TIME_FORMAT)} and {query_end_time.strftime(DOY_TIME_FORMAT)}."
        logger.warning(msg)
    if return_on == ReturnOn.ALL and not (results['measurements_for_all']):
        msg = f"EHA measurements were not located for all channels: {results['channels_with_no_data']} between:  {query_start_time.strftime(DOY_TIME_FORMAT)} and {query_end_time.strftime(DOY_TIME_FORMAT)}."
        logger.warning(msg)

    return results


def get_evrs(session_ids, timeout, lookback, evr_names=[], evr_ids=[],
             evr_levels=[], evr_messages=[], start_time=None, fsw_sse=None,
             rt_rec=None, max_results=_LAD_EVR_MAX_RESULTS):
    """
    This function will query the GLAD for specific EVR(s) that match the name/id/level/message filters and will
    continue to query until an evr is found or the timeout is reached. It will then format the data.

    Note that this function only operates with ERT.

    Parameters
    ----------
    session_ids: list of int
        AMPCS session ids Note that multi-session queries, while possible, have max_result implications and are not
        handled by the functions that evaluate the results.
    timeout: int
        How much time (seconds) to look for the EVR before giving up
    lookback: int
        How much time (seconds) to "look back" from now for the EVR
    evr_names: list of str
        EVR(s) to query for (by name). Wildcards ('*') are supported but will not work at the end of Names
        (example: *NO_OP* will not locate CMD_SVC_NO_OP but *NO_OP will)
    evr_ids: list of int
        EVR(s) to query for (by id)
    evr_levels: list of str
        EVR Level(s) to query for Wildcards ('*') are supported
    evr_messages: list of str
        Can use wild cards ('*') and regular expressions.
    start_time: datetime object
        The start time of the query (use now if not provided)
    fsw_sse: FSWvsSSE
        Query SSE or FSW EVRs
    rt_rec: RealTimeRecorded
        Whether to query real time or recorded EVRs
    max_results: int
        The max results to return from the evr query
    Returns
    -------
        List of EVR objects ordered by ERT in descending order (the first is the latest)
    """

    if not start_time:
        start_time = datetime.utcnow()

    query_start_time = start_time - timedelta(seconds=lookback)
    query_end_time = start_time + timedelta(seconds=timeout)

    time_out_time = query_end_time + timedelta(seconds=_AMPCS_QUERY_MARGIN)

    query_once = False
    while (not query_once) or datetime.utcnow() < time_out_time:
        query_once = True
        # Queries the evr

        try:
            query_results = query_evrs(session_ids,
                                       evr_names=evr_names,
                                       evr_ids=evr_ids,
                                       evr_levels=evr_levels,
                                       evr_messages=evr_messages,
                                       start_time=query_start_time.strftime(DOY_TIME_FORMAT),
                                       end_time=query_end_time.strftime(DOY_TIME_FORMAT),
                                       fsw_sse=fsw_sse,
                                       rt_rec=rt_rec,
                                       max_results=max_results)
        except:
            msg = 'Encountered and error querying GLAD for EVRS'
            logger.error(msg)
            logger.error(traceback.format_exc())
            raise QueryError(msg)

        # if results are returned, convert, and exit
        if query_results:
            # There is no guarantee in the order of query results.
            # Sort by ERT in descending order (the first is the latest).
            query_results = sorted(query_results, key=itemgetter('ert'), reverse=True)

            msg = f'Located:{len(query_results)} EVRs between {query_start_time.strftime(DOY_TIME_FORMAT)} and {query_end_time.strftime(DOY_TIME_FORMAT)} that match the provided filters.'
            logger.info(msg)

            return query_results

        # Wait a second to avoid hammer the GLAD
        time.sleep(1)

    msg = f"Could not locate any EVRS that matched the provided filters between {query_start_time.strftime(DOY_TIME_FORMAT)} and {query_end_time.strftime(DOY_TIME_FORMAT)}."
    logger.warning(msg)

    return query_results
